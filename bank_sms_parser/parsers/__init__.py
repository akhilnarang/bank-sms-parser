"""Bank parser registry."""

from bank_sms_parser.parsers.axis import AxisParser
from bank_sms_parser.parsers.equitas import EquitasParser
from bank_sms_parser.parsers.hdfc import HdfcParser

PARSERS: dict[str, type] = {
    "axis": AxisParser,
    "equitas": EquitasParser,
    "hdfc": HdfcParser,
}

__all__ = ["PARSERS"]
