"""Pydantic models for parsed SMS output."""

from datetime import date, time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class Money(BaseModel):
    amount: Decimal = Field(ge=0)
    currency: str = "INR"


class SmsTransactionAlert(BaseModel):
    direction: Literal["debit", "credit", "declined"]
    amount: Money
    transaction_date: date | None = None
    transaction_time: time | None = None
    counterparty: str | None = None
    balance: Money | None = None
    reference_number: str | None = None
    account_mask: str | None = None
    card_mask: str | None = None
    channel: str | None = None
    raw_description: str | None = Field(
        default=None,
        exclude=True,
        repr=False,
        description="Debug-only raw parser context; excluded from serialized output by default.",
    )
