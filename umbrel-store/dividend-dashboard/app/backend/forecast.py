"""Dividendprognose-logica op basis van historische betalingen uit yfinance."""

from collections import defaultdict
from datetime import datetime, timedelta

import pandas as pd


def trailing_12m_dividends_per_share(div_history) -> float:
    if div_history is None or len(div_history) == 0:
        return 0.0
    last_date = div_history.index.max()
    cutoff = last_date - pd.Timedelta(days=365)
    recent = div_history[div_history.index >= cutoff]
    return float(recent.sum())


def monthly_distribution_weights(div_history) -> dict:
    """Geeft per maand (1-12) het aandeel van het jaarlijkse dividend dat
    historisch in die maand werd uitgekeerd, o.b.v. de laatste 12 maanden."""
    if div_history is None or len(div_history) == 0:
        return {}
    last_date = div_history.index.max()
    cutoff = last_date - pd.Timedelta(days=365)
    recent = div_history[div_history.index >= cutoff]
    total = float(recent.sum())
    if total <= 0:
        return {}
    weights: dict[int, float] = defaultdict(float)
    for ts, amount in recent.items():
        weights[ts.month] += float(amount) / total
    return dict(weights)


def estimate_next_payment_date(div_history, ex_dividend_date: str | None = None):
    """Volgende ex-dividenddatum: gebruikt de datum uit yfinance-info als die
    in de toekomst ligt, anders een schatting o.b.v. de gemiddelde historische
    betaalfrequentie."""
    today = datetime.utcnow().date()

    if ex_dividend_date:
        try:
            d = datetime.fromisoformat(ex_dividend_date).date()
            if d >= today:
                return d, False
        except Exception:
            pass

    if div_history is None or len(div_history) < 2:
        return None, True

    dates = sorted(div_history.index.to_pydatetime())
    intervals = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
    recent_intervals = intervals[-4:] if intervals else []
    if not recent_intervals:
        return None, True
    avg_interval = sum(recent_intervals) / len(recent_intervals)

    next_date = dates[-1].date()
    while next_date < today:
        next_date = next_date + timedelta(days=avg_interval)
    return next_date, True
