const API = "/api";

const els = {
  totals: document.getElementById("totals"),
  holdingsBody: document.querySelector("#holdings-table tbody"),
  calendarBody: document.querySelector("#calendar-table tbody"),
  forecastSummary: document.getElementById("forecast-summary"),
  refreshBtn: document.getElementById("refresh-btn"),
  addBtn: document.getElementById("add-holding-btn"),
  dialog: document.getElementById("holding-dialog"),
  form: document.getElementById("holding-form"),
  cancelBtn: document.getElementById("cancel-btn"),
  dialogTitle: document.getElementById("dialog-title"),
  tickerInput: document.getElementById("f-ticker"),
  tickerSuggestions: document.getElementById("ticker-suggestions"),
};

let forecastChart, sectorChart;

const eur = (n) => new Intl.NumberFormat("nl-NL", { style: "currency", currency: "EUR" }).format(n || 0);
const pct = (n) => `${(n ?? 0).toFixed(2)}%`;

async function api(path, options = {}) {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Fout bij ${path}`);
  }
  return res.json();
}

async function loadAll(force = false) {
  const q = force ? "?force=true" : "";
  const [summary, forecast, calendar] = await Promise.all([
    api(`/portfolio/summary${q}`),
    api(`/dividends/forecast${q}`),
    api(`/dividends/calendar${q}`),
  ]);
  renderTotals(summary.totals);
  renderHoldings(summary.holdings);
  renderSectorChart(summary.sectors);
  renderForecast(forecast);
  renderCalendar(calendar.events);
}

function renderTotals(totals) {
  const cards = [
    ["Totale waarde", eur(totals.value_eur)],
    ["Ongerealiseerd rendement", `${eur(totals.gain_eur)} (${pct(totals.gain_pct)})`],
    ["Verwacht jaarlijks dividend", eur(totals.annual_dividend_income_eur)],
    ["Portfolio dividendrendement", pct(totals.portfolio_yield_pct)],
  ];
  els.totals.innerHTML = cards
    .map(
      ([label, value]) => `
      <div class="stat">
        <span class="stat-label">${label}</span>
        <span class="stat-value">${value}</span>
      </div>`
    )
    .join("");
}

function renderHoldings(holdings) {
  if (!holdings.length) {
    els.holdingsBody.innerHTML = `<tr><td colspan="10" class="muted">Nog geen aandelen toegevoegd.</td></tr>`;
    return;
  }
  els.holdingsBody.innerHTML = holdings
    .map(
      (h) => `
      <tr data-id="${h.id}">
        <td>${h.ticker}</td>
        <td>${h.name}</td>
        <td>${h.sector}</td>
        <td>${h.shares}</td>
        <td>${h.price_native ?? "-"} ${h.currency}</td>
        <td>${eur(h.current_value_eur)}</td>
        <td class="${h.gain_eur >= 0 ? "positive" : "negative"}">${eur(h.gain_eur)} (${pct(h.gain_pct)})</td>
        <td>${pct(h.current_yield_pct)}</td>
        <td>${pct(h.yield_on_cost_pct)}</td>
        <td>
          <button class="icon-btn edit-btn" data-id="${h.id}" title="Bewerken">&#9998;</button>
          <button class="icon-btn delete-btn" data-id="${h.id}" title="Verwijderen">&#10005;</button>
        </td>
      </tr>`
    )
    .join("");
}

function renderForecast(forecast) {
  const ctx = document.getElementById("forecast-chart");
  const data = {
    labels: forecast.monthly.map((m) => m.month),
    datasets: [
      {
        label: "Verwacht dividend (EUR)",
        data: forecast.monthly.map((m) => m.amount_eur),
        backgroundColor: "#2f6f4f",
      },
    ],
  };
  if (forecastChart) {
    forecastChart.data = data;
    forecastChart.update();
  } else {
    forecastChart = new Chart(ctx, {
      type: "bar",
      data,
      options: {
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true } },
      },
    });
  }
  els.forecastSummary.textContent = `Jaartotaal: ${eur(forecast.annual_total_eur)} · Gemiddeld per maand: ${eur(forecast.monthly_average_eur)}`;
}

const SECTOR_COLORS = ["#2f6f4f", "#4d8f6a", "#7bb896", "#a9d4bf", "#c96a4f", "#e0a458", "#5a7ea6", "#8a6fb0", "#b0b0b0", "#d0c05a"];

function renderSectorChart(sectors) {
  const ctx = document.getElementById("sector-chart");
  const data = {
    labels: sectors.map((s) => s.sector),
    datasets: [
      {
        data: sectors.map((s) => s.value_eur),
        backgroundColor: sectors.map((_, i) => SECTOR_COLORS[i % SECTOR_COLORS.length]),
      },
    ],
  };
  if (sectorChart) {
    sectorChart.data = data;
    sectorChart.update();
  } else {
    sectorChart = new Chart(ctx, {
      type: "doughnut",
      data,
      options: { plugins: { legend: { position: "bottom" } } },
    });
  }
}

function renderCalendar(events) {
  if (!events.length) {
    els.calendarBody.innerHTML = `<tr><td colspan="4" class="muted">Geen aankomende data gevonden.</td></tr>`;
    return;
  }
  els.calendarBody.innerHTML = events
    .map(
      (e) => `
      <tr>
        <td>${new Date(e.next_ex_dividend_date).toLocaleDateString("nl-NL")}</td>
        <td>${e.ticker}</td>
        <td>${e.name}</td>
        <td>${e.estimated ? '<span class="badge">geschat</span>' : ""}</td>
      </tr>`
    )
    .join("");
}

// ---- Dialoog / formulier ----

function openDialog(holding = null) {
  els.form.reset();
  hideSuggestions();
  document.getElementById("holding-id").value = holding?.id || "";
  els.dialogTitle.textContent = holding ? "Aandeel bewerken" : "Aandeel toevoegen";
  if (holding) {
    document.getElementById("f-ticker").value = holding.ticker;
    document.getElementById("f-shares").value = holding.shares;
    document.getElementById("f-cost").value = holding.cost_basis;
    document.getElementById("f-date").value = holding.purchase_date;
    document.getElementById("f-currency").value = holding.currency;
  }
  els.dialog.showModal();
}

// ---- Ticker zoeken (autocomplete) ----

let searchDebounce;

function hideSuggestions() {
  els.tickerSuggestions.innerHTML = "";
  els.tickerSuggestions.classList.remove("open");
}

function renderSuggestions(results) {
  if (!results.length) {
    hideSuggestions();
    return;
  }
  els.tickerSuggestions.innerHTML = results
    .map(
      (r) => `
      <div class="suggestion-item" data-symbol="${r.symbol}">
        <span class="suggestion-symbol">${r.symbol}</span>
        <span class="suggestion-name">${r.name}</span>
        <span class="suggestion-meta">${[r.exchange, r.type].filter(Boolean).join(" · ")}</span>
      </div>`
    )
    .join("");
  els.tickerSuggestions.classList.add("open");
}

els.tickerInput.addEventListener("input", () => {
  const query = els.tickerInput.value.trim();
  clearTimeout(searchDebounce);
  if (query.length < 1) {
    hideSuggestions();
    return;
  }
  searchDebounce = setTimeout(async () => {
    try {
      const data = await api(`/search?q=${encodeURIComponent(query)}`);
      renderSuggestions(data.results);
    } catch {
      hideSuggestions();
    }
  }, 300);
});

els.tickerSuggestions.addEventListener("click", (e) => {
  const item = e.target.closest(".suggestion-item");
  if (!item) return;
  els.tickerInput.value = item.dataset.symbol;
  hideSuggestions();
});

document.addEventListener("click", (e) => {
  if (!e.target.closest(".autocomplete-wrap")) hideSuggestions();
});

els.addBtn.addEventListener("click", () => openDialog());
els.cancelBtn.addEventListener("click", () => els.dialog.close());
els.refreshBtn.addEventListener("click", () => loadAll(true));

els.holdingsBody.addEventListener("click", async (e) => {
  const target = e.target;
  if (target.classList.contains("edit-btn")) {
    const holdings = await api("/holdings");
    const holding = holdings.find((h) => String(h.id) === target.dataset.id);
    openDialog(holding);
  }
  if (target.classList.contains("delete-btn")) {
    if (confirm("Dit aandeel verwijderen?")) {
      await api(`/holdings/${target.dataset.id}`, { method: "DELETE" });
      await loadAll();
    }
  }
});

els.form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = document.getElementById("holding-id").value;
  const payload = {
    ticker: document.getElementById("f-ticker").value.trim().toUpperCase(),
    shares: parseFloat(document.getElementById("f-shares").value),
    cost_basis: parseFloat(document.getElementById("f-cost").value),
    purchase_date: document.getElementById("f-date").value,
    currency: document.getElementById("f-currency").value,
  };
  try {
    if (id) {
      await api(`/holdings/${id}`, { method: "PUT", body: JSON.stringify(payload) });
    } else {
      await api("/holdings", { method: "POST", body: JSON.stringify(payload) });
    }
    els.dialog.close();
    await loadAll();
  } catch (err) {
    alert(err.message);
  }
});

loadAll();
