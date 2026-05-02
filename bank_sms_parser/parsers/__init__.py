"""Bank parser registry."""

from bank_sms_parser.parsers.axis import AxisParser
from bank_sms_parser.parsers.equitas import EquitasParser
from bank_sms_parser.parsers.hdfc import HdfcParser
from bank_sms_parser.parsers.idfc import IdfcParser
from bank_sms_parser.parsers.indusind import IndusindParser

PARSERS: dict[str, type] = {
    "axis": AxisParser,
    "equitas": EquitasParser,
    "hdfc": HdfcParser,
    "idfc": IdfcParser,
    "indusind": IndusindParser,
}

__all__ = ["PARSERS"]
