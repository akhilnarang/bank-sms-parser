"""Pydantic models for parsed SMS output."""

from decimal import Decimal

from pydantic import BaseModel, Field


class Money(BaseModel):
    amount: Decimal = Field(ge=0)
    currency: str = "INR"
