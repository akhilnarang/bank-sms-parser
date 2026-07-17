"""Pydantic models for parsed SMS output."""

from datetime import date, time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


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


class ParsedSms(BaseModel):
    email_type: str
    bank: str
    transaction: SmsTransactionAlert | None = None

    ledger_role: Literal["primary", "provisional", "restatement"] = "primary"
    """This message's relation to the money event, not a policy for it.

    - ``primary``: the message that carries the event into the ledger (default;
      every ordinary alert).
    - ``provisional``: a pre-announcement whose ledger event is a *later*
      message (e.g. a payment "received" notice ahead of its settlement).
    - ``restatement``: a redundant confirmation of an *earlier* message that
      already carried the event (e.g. a "thank you for the payment" echo).

    A consumer decides what to do with a non-``primary`` role (record no row,
    notify differently); the parser only states the fact. Meaningful only when
    ``transaction`` is set. It does NOT encode "not a transaction" (that is
    ``transaction is None``) nor a declined outcome (that is
    ``transaction.direction == "declined"``) — those are orthogonal axes.
    """

    @model_validator(mode="after")
    def _role_requires_transaction(self) -> ParsedSms:
        if self.ledger_role != "primary" and self.transaction is None:
            raise ValueError(
                f"ledger_role={self.ledger_role!r} is meaningless without a transaction"
            )
        return self
