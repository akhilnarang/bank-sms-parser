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

    ledger_role: Literal["primary", "provisional", "restatement", "completion"] = (
        "primary"
    )
    """This message's relation to the money event, not a policy for it.

    - ``primary``: the message that carries the event into the ledger (default;
      every ordinary alert).
    - ``provisional``: a pre-announcement whose ledger event is a *later*
      message (e.g. a payment "received" notice ahead of its settlement).
    - ``restatement``: a redundant confirmation of an *earlier* message that
      already carried the event (e.g. a "thank you for the payment" echo).
    - ``completion``: a *later* message that supplies a field the primary
      message lacked — typically a reference — for the same event an *earlier*
      message already recorded (e.g. an RTGS settlement carrying the UTR for a
      submission alert that named only the account). The consumer completes the
      earlier row and records no new row of its own.

    A consumer decides what to do with a non-``primary`` role (record no row,
    notify differently); the parser only states the fact. Meaningful only when
    ``transaction`` is set. It does NOT encode "not a transaction" (that is
    ``transaction is None``) nor a declined outcome (that is
    ``transaction.direction == "declined"``) — those are orthogonal axes.
    """

    event_time_source: Literal["body", "message_arrival"] = "body"
    """Where the time of the event comes from, not a policy for it.

    - ``body``: the bank writes the time in the message, or the message has
      no time that you can use (default; almost every parser).
    - ``message_arrival``: the body has no time, and this bank sends the
      message at the moment of the transaction. The consumer can thus use
      the time at which the phone receives the message in place of the time
      of the event.

    A consumer decides what to do with ``message_arrival``. It must trust
    such a time less than a time that the bank writes. The parser only states
    the fact. Set this value on the parser class. The dispatcher copies the
    value to each result.
    """

    identifies_by: Literal["counterparty", "card_mask", "none"] = "counterparty"
    """Which field shows which event this message reports, when the
    counterparty cannot show it.

    - ``counterparty``: the message names a merchant or a payer, and that
      name shows the event (default).
    - ``card_mask``: the message reports a payment of your own card bill.
      The payer is you, so there is no merchant to name. The card mask shows
      which event this is.
    - ``none``: the bank sends no field that shows the event. Two payments of
      the same amount on the same day are thus alike in every field. The
      consumer must ask a person, or keep both rows.

    The parser only states the fact. Set this value on the parser class. The
    dispatcher copies the value to each result.
    """

    @model_validator(mode="after")
    def _role_requires_transaction(self) -> ParsedSms:
        if self.ledger_role != "primary" and self.transaction is None:
            raise ValueError(
                f"ledger_role={self.ledger_role!r} is meaningless without a transaction"
            )
        return self
