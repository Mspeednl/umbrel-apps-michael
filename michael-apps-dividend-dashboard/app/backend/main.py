import os
from collections import defaultdict
from typing import List

import market_data as md
import forecast as fc
from db import get_session, init_db
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from models import Holding, HoldingCreate, HoldingUpdate
from sqlmodel import Session, select

app = FastAPI(title="Dividend Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


# ---------- Holdings CRUD ----------


@app.get("/api/holdings", response_model=List[Holding])
def list_holdings(session: Session = Depends(get_session)):
    return session.exec(select(Holding)).all()


@app.post("/api/holdings", response_model=Holding)
def create_holding(payload: HoldingCreate, session: Session = Depends(get_session)):
    holding = Holding(**payload.model_dump())
    session.add(holding)
    session.commit()
    session.refresh(holding)
    return holding


@app.put("/api/holdings/{holding_id}", response_model=Holding)
def update_holding(holding_id: int, payload: HoldingUpdate, session: Session = Depends(get_session)):
    holding = session.get(Holding, holding_id)
    if not holding:
        raise HTTPException(status_code=404, detail="Holding niet gevonden")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(holding, key, value)
    session.add(holding)
    session.commit()
    session.refresh(holding)
    return holding


@app.delete("/api/holdings/{holding_id}")
def delete_holding(holding_id: int, session: Session = Depends(get_session)):
    holding = session.get(Holding, holding_id)
    if not holding:
        raise HTTPException(status_code=404, detail="Holding niet gevonden")
    session.delete(holding)
    session.commit()
    return {"ok": True}


# ---------- Ticker zoeken ----------


@app.get("/api/search")
def search_ticker(q: str = Query(..., min_length=1)):
    return {"results": md.search_symbols(q)}


# ---------- Portfolio overzicht ----------


def _enrich_holding(holding: Holding, force: bool) -> dict:
    quote = md.get_quote(holding.ticker, force=force)
    price_fx = md.get_fx_rate(quote["currency"], force=force)
    cost_fx = md.get_fx_rate(holding.currency, force=force)

    price = quote["price"] or 0.0
    current_value_eur = price * holding.shares * price_fx
    cost_value_eur = holding.cost_basis * holding.shares * cost_fx
    gain_eur = current_value_eur - cost_value_eur
    gain_pct = (gain_eur / cost_value_eur * 100) if cost_value_eur else 0.0

    div_hist = md.get_dividend_history(holding.ticker, force=force)
    annual_div_per_share = fc.trailing_12m_dividends_per_share(div_hist)
    annual_income_eur = annual_div_per_share * holding.shares * price_fx
    current_yield_pct = (annual_div_per_share / price * 100) if price else 0.0
    yield_on_cost_pct = (annual_income_eur / cost_value_eur * 100) if cost_value_eur else 0.0

    return {
        "id": holding.id,
        "ticker": holding.ticker,
        "name": quote["name"],
        "sector": quote["sector"],
        "shares": holding.shares,
        "currency": quote["currency"],
        "price_native": round(price, 2) if price else None,
        "cost_basis": holding.cost_basis,
        "current_value_eur": round(current_value_eur, 2),
        "cost_value_eur": round(cost_value_eur, 2),
        "gain_eur": round(gain_eur, 2),
        "gain_pct": round(gain_pct, 2),
        "annual_dividend_income_eur": round(annual_income_eur, 2),
        "current_yield_pct": round(current_yield_pct, 2),
        "yield_on_cost_pct": round(yield_on_cost_pct, 2),
    }


@app.get("/api/portfolio/summary")
def portfolio_summary(force: bool = Query(False), session: Session = Depends(get_session)):
    holdings = session.exec(select(Holding)).all()
    rows = [_enrich_holding(h, force) for h in holdings]

    total_value = sum(r["current_value_eur"] for r in rows)
    total_cost = sum(r["cost_value_eur"] for r in rows)
    total_gain = total_value - total_cost
    total_gain_pct = (total_gain / total_cost * 100) if total_cost else 0.0
    total_annual_income = sum(r["annual_dividend_income_eur"] for r in rows)

    sector_totals: dict[str, float] = defaultdict(float)
    for r in rows:
        sector_totals[r["sector"]] += r["current_value_eur"]

    sectors = [
        {
            "sector": s,
            "value_eur": round(v, 2),
            "pct": round((v / total_value * 100) if total_value else 0.0, 2),
        }
        for s, v in sorted(sector_totals.items(), key=lambda kv: -kv[1])
    ]

    return {
        "holdings": rows,
        "totals": {
            "value_eur": round(total_value, 2),
            "cost_eur": round(total_cost, 2),
            "gain_eur": round(total_gain, 2),
            "gain_pct": round(total_gain_pct, 2),
            "annual_dividend_income_eur": round(total_annual_income, 2),
            "portfolio_yield_pct": round((total_annual_income / total_value * 100) if total_value else 0.0, 2),
        },
        "sectors": sectors,
    }


# ---------- Dividend forecast ----------

MONTH_NAMES_NL = ["", "Jan", "Feb", "Mrt", "Apr", "Mei", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dec"]


@app.get("/api/dividends/forecast")
def dividend_forecast(force: bool = Query(False), session: Session = Depends(get_session)):
    holdings = session.exec(select(Holding)).all()
    monthly_totals: dict[int, float] = defaultdict(float)
    per_holding = []

    for h in holdings:
        quote = md.get_quote(h.ticker, force=force)
        price_fx = md.get_fx_rate(quote["currency"], force=force)
        cost_fx = md.get_fx_rate(h.currency, force=force)

        div_hist = md.get_dividend_history(h.ticker, force=force)
        annual_per_share = fc.trailing_12m_dividends_per_share(div_hist)
        annual_income_eur = annual_per_share * h.shares * price_fx
        weights = fc.monthly_distribution_weights(div_hist)
        cost_value_eur = h.cost_basis * h.shares * cost_fx

        for month, weight in weights.items():
            monthly_totals[month] += annual_income_eur * weight

        per_holding.append(
            {
                "ticker": h.ticker,
                "name": quote["name"],
                "annual_income_eur": round(annual_income_eur, 2),
                "yield_on_cost_pct": round((annual_income_eur / cost_value_eur * 100) if cost_value_eur else 0.0, 2),
            }
        )

    monthly = [
        {"month": MONTH_NAMES_NL[m], "amount_eur": round(monthly_totals.get(m, 0.0), 2)}
        for m in range(1, 13)
    ]
    annual_total = sum(monthly_totals.values())

    return {
        "monthly": monthly,
        "annual_total_eur": round(annual_total, 2),
        "monthly_average_eur": round(annual_total / 12, 2) if annual_total else 0.0,
        "per_holding": sorted(per_holding, key=lambda r: -r["annual_income_eur"]),
    }


# ---------- Dividend kalender ----------


@app.get("/api/dividends/calendar")
def dividend_calendar(force: bool = Query(False), session: Session = Depends(get_session)):
    holdings = session.exec(select(Holding)).all()
    events = []
    for h in holdings:
        quote = md.get_quote(h.ticker, force=force)
        div_hist = md.get_dividend_history(h.ticker, force=force)
        next_date, estimated = fc.estimate_next_payment_date(div_hist, quote.get("ex_dividend_date"))
        if next_date:
            events.append(
                {
                    "ticker": h.ticker,
                    "name": quote["name"],
                    "next_ex_dividend_date": next_date.isoformat(),
                    "estimated": estimated,
                }
            )
    events.sort(key=lambda e: e["next_ex_dividend_date"])
    return {"events": events}


# ---------- Statische frontend ----------

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
