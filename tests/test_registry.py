"""Registry hygiene + filesystem parity + import stability."""

from collections.abc import Sequence
from importlib import import_module
from pathlib import Path

import pytest
from bank_sms_parser.api import SUPPORTED_BANKS
from bank_sms_parser.parsers import PARSERS
from bank_sms_parser.parsers.base import BankSmsParser, BaseSmsParser

PARSER_DIR = Path(__file__).resolve().parents[1] / "bank_sms_parser" / "parsers"


def test_supported_banks_matches_parsers() -> None:
    assert SUPPORTED_BANKS == tuple(PARSERS)


def test_supported_banks_non_empty() -> None:
    assert len(SUPPORTED_BANKS) > 0


def test_filesystem_matches_registry() -> None:
    """Every parser file/subpackage corresponds to a PARSERS key, and vice versa."""
    filesystem_banks: set[str] = set()
    for path in PARSER_DIR.iterdir():
        if path.name in {"__init__.py", "base.py", "__pycache__"}:
            continue
        if path.name.startswith("_"):
            continue
        filesystem_banks.add(path.stem if path.is_file() else path.name)
    assert filesystem_banks == set(PARSERS)


def test_bank_dispatchers_declare_required_class_attrs() -> None:
    for slug, parser_cls in PARSERS.items():
        assert isinstance(parser_cls.bank, str)
        assert isinstance(parser_cls.parsers, Sequence)
        assert len(parser_cls.parsers) > 0
        for parser in parser_cls.parsers:
            assert isinstance(parser, BaseSmsParser)
        # The dispatcher's bank slug must match the registry key.
        assert parser_cls.bank == slug


def test_individual_parser_email_types_unique_per_bank() -> None:
    """Within a single bank's parser chain, no two parser classes may share email_type.

    (Multiple compiled regexes inside ONE class is fine — that's the OneCard
    pattern. This rule is about *class-level* uniqueness.)
    """
    for slug, parser_cls in PARSERS.items():
        seen: set[str] = set()
        for parser in parser_cls.parsers:
            assert parser.email_type not in seen, (
                f"{slug}: duplicate email_type {parser.email_type!r}"
            )
            seen.add(parser.email_type)


def test_email_types_are_bank_prefixed() -> None:
    for slug, parser_cls in PARSERS.items():
        for parser in parser_cls.parsers:
            assert parser.email_type.startswith(f"{slug}_"), (
                f"{slug}: parser {type(parser).__name__} has email_type "
                f"{parser.email_type!r} not prefixed with {slug!r}"
            )


def test_bank_slugs_are_lowercase_ascii() -> None:
    for slug in PARSERS:
        assert slug == slug.lower()
        assert slug.isascii()


def test_bank_module_exposes_dispatcher_and_parse() -> None:
    """Each bank module/subpackage exposes its dispatcher class and a callable parse()."""
    for slug, parser_cls in PARSERS.items():
        module = import_module(f"bank_sms_parser.parsers.{slug}")
        assert getattr(module, parser_cls.__name__) is parser_cls
        assert callable(module.parse)


@pytest.mark.parametrize("slug, dispatcher_cls", list(PARSERS.items()))
def test_module_level_parse_forwards_kwargs(slug, dispatcher_cls, monkeypatch) -> None:
    """For each bank, the module-level `parse(body, *, sender, received_at)` forwards both kwargs."""
    import datetime
    from decimal import Decimal

    from bank_sms_parser.models import Money, ParsedSms, SmsTransactionAlert

    received: dict = {}

    class _RecordingParser(BaseSmsParser):
        bank = "stub"
        email_type = "stub_alert"

        def parse(self, body, *, sender=None, received_at=None):
            received["sender"] = sender
            received["received_at"] = received_at
            return ParsedSms(
                email_type=self.email_type,
                bank="stub",
                transaction=SmsTransactionAlert(
                    direction="debit",
                    amount=Money(amount=Decimal("1")),
                ),
            )

    class _StubDispatcher(BankSmsParser):
        bank = "stub"
        parsers = (_RecordingParser(),)

    module = import_module(f"bank_sms_parser.parsers.{slug}")
    dispatcher_class_name = dispatcher_cls.__name__
    monkeypatch.setattr(module, dispatcher_class_name, _StubDispatcher)

    ts = datetime.datetime(2026, 5, 2, 14, 23, 11, tzinfo=datetime.UTC)
    module.parse("any body", sender="VK-TEST", received_at=ts)

    assert received["sender"] == "VK-TEST"
    assert received["received_at"] == ts
