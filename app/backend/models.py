from datetime import date
from typing import Optional

from sqlmodel import Field, SQLModel


class Holding(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ticker: str
    shares: float
    cost_basis: float  # aankoopprijs per aandeel, in de valuta van de holding
    purchase_date: date
    currency: str = "EUR"


class HoldingCreate(SQLModel):
    ticker: str
    shares: float
    cost_basis: float
    purchase_date: date
    currency: str = "EUR"


class HoldingUpdate(SQLModel):
    ticker: Optional[str] = None
    shares: Optional[float] = None
    cost_basis: Optional[float] = None
    purchase_date: Optional[date] = None
    currency: Optional[str] = None
