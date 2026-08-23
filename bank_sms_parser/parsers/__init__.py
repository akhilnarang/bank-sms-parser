"""Bank parser registry."""

from bank_sms_parser.parsers.axis import AxisParser
from bank_sms_parser.parsers.base import BankSmsParser
from bank_sms_parser.parsers.equitas import EquitasParser
from bank_sms_parser.parsers.hdfc import HdfcParser
from bank_sms_parser.parsers.hsbc import HsbcParser
from bank_sms_parser.parsers.icici import IciciParser
from bank_sms_parser.parsers.idfc import IdfcParser
from bank_sms_parser.parsers.indusind import IndusindParser
from bank_sms_parser.parsers.jupiter import JupiterParser
from bank_sms_parser.parsers.kotak import KotakParser
from bank_sms_parser.parsers.onecard import OnecardParser
from bank_sms_parser.parsers.revolut import RevolutParser
from bank_sms_parser.parsers.sbi import SbiParser
from bank_sms_parser.parsers.slice import SliceParser

PARSERS: dict[str, type[BankSmsParser]] = {
    "axis": AxisParser,
    "equitas": EquitasParser,
    "hdfc": HdfcParser,
    "hsbc": HsbcParser,
    "icici": IciciParser,
    "idfc": IdfcParser,
    "indusind": IndusindParser,
    "jupiter": JupiterParser,
    "kotak": KotakParser,
    "onecard": OnecardParser,
    "revolut": RevolutParser,
    "sbi": SbiParser,
    "slice": SliceParser,
}

__all__ = ["PARSERS"]
