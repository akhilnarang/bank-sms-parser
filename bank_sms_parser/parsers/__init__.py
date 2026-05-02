"""Bank parser registry."""

from bank_sms_parser.parsers.hdfc import HdfcParser

PARSERS: dict[str, type] = {
    "hdfc": HdfcParser,
}

__all__ = ["PARSERS"]
