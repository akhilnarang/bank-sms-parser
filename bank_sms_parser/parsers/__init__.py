"""Bank parser registry."""

from bank_sms_parser.parsers.equitas import EquitasParser
from bank_sms_parser.parsers.hdfc import HdfcParser

PARSERS: dict[str, type] = {
    "equitas": EquitasParser,
    "hdfc": HdfcParser,
}

__all__ = ["PARSERS"]
