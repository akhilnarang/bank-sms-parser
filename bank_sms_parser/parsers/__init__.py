"""Bank parser registry."""

from bank_sms_parser.parsers.axis import AxisParser
from bank_sms_parser.parsers.base import BankSmsParser
from bank_sms_parser.parsers.equitas import EquitasParser
from bank_sms_parser.parsers.hdfc import HdfcParser
from bank_sms_parser.parsers.icici import IciciParser
from bank_sms_parser.parsers.idfc import IdfcParser
from bank_sms_parser.parsers.indusind import IndusindParser
from bank_sms_parser.parsers.onecard import OnecardParser
from bank_sms_parser.parsers.slice import SliceParser

PARSERS: dict[str, type[BankSmsParser]] = {
    "axis": AxisParser,
    "equitas": EquitasParser,
    "hdfc": HdfcParser,
    "icici": IciciParser,
    "idfc": IdfcParser,
    "indusind": IndusindParser,
    "onecard": OnecardParser,
    "slice": SliceParser,
}

__all__ = ["PARSERS"]
