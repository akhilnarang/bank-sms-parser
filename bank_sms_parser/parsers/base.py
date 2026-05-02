"""Base parser ABC, bank-level dispatcher, and fallback-chain executor."""

import datetime
import warnings
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import ClassVar

from bank_sms_parser.exceptions import ParseError, ParserStubError
from bank_sms_parser.models import ParsedSms


class BaseSmsParser(ABC):
    bank: str
    email_type: str

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # Skip classes that don't define either attribute — abstract intermediates.
        if "bank" not in cls.__dict__ and "email_type" not in cls.__dict__:
            return
        bank = getattr(cls, "bank", None)
        email_type = getattr(cls, "email_type", None)
        if not isinstance(bank, str):
            raise TypeError(f"{cls.__name__} must define a 'bank: str' class attribute")
        if not isinstance(email_type, str):
            raise TypeError(
                f"{cls.__name__} must define an 'email_type: str' class attribute"
            )

    @abstractmethod
    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        """Parse a single SMS body into a ParsedSms or raise ParseError."""
        ...


class BankSmsParser:
    """Bank-level dispatcher that preserves per-bank parser ordering."""

    bank: ClassVar[str]
    parsers: ClassVar[Sequence[BaseSmsParser]]

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if "bank" not in cls.__dict__ and "parsers" not in cls.__dict__:
            return
        bank = getattr(cls, "bank", None)
        bank_parsers = getattr(cls, "parsers", None)
        if not isinstance(bank, str):
            raise TypeError(f"{cls.__name__} must define a 'bank: str' class attribute")
        if not isinstance(bank_parsers, Sequence):
            raise TypeError(
                f"{cls.__name__} must define a 'parsers' sequence of parser instances"
            )

    def parse(
        self,
        body: str,
        *,
        sender: str | None = None,
        received_at: datetime.datetime | None = None,
    ) -> ParsedSms:
        return parse_with_parsers(
            self.bank, body, self.parsers, sender=sender, received_at=received_at
        )


def parse_with_parsers(
    bank: str,
    body: str,
    parsers: Sequence[BaseSmsParser],
    *,
    sender: str | None = None,
    received_at: datetime.datetime | None = None,
) -> ParsedSms:
    """Try each parser in order; first one that returns a ParsedSms wins.

    ParseError / ParserStubError → continue to next parser.
    Unexpected exceptions are collected (so a bug in one parser does not
    silently shadow the others) and surface in the final ParseError if no
    parser matches.
    """
    errors: list[str] = []
    unexpected_errors: list[Exception] = []
    for parser in parsers:
        try:
            result = parser.parse(body, sender=sender, received_at=received_at)
        except (ParseError, ParserStubError) as exc:
            errors.append(f"{parser.email_type}: {type(exc).__name__}")
            continue
        except Exception as exc:
            errors.append(f"{parser.email_type}: {type(exc).__name__}: {exc}")
            unexpected_errors.append(exc)
            continue
        if unexpected_errors:
            warnings.warn(
                f"Parser {parser.email_type} succeeded but earlier parsers "
                "raised unexpected errors: "
                + "; ".join(
                    f"{type(e).__name__}: {e}" for e in unexpected_errors
                ),
                stacklevel=2,
            )
        return result

    msg = (
        f"No parser for bank {bank!r} could handle this SMS. "
        f"Tried: {', '.join(p.email_type for p in parsers)}. "
        f"Errors: {'; '.join(errors)}"
    )
    exc = ParseError(msg)
    if unexpected_errors:
        exc.__cause__ = (
            unexpected_errors[0]
            if len(unexpected_errors) == 1
            else ExceptionGroup("Unexpected parser errors", unexpected_errors)
        )
    raise exc
