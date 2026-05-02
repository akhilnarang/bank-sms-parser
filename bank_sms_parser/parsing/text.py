"""Text helpers for SMS bodies."""

import re

# Card mask comes in many shapes:
#   "x0000"          (HDFC, lowercase x prefix)
#   "XX0000"         (most banks)
#   "*XX0000"        (IndusInd, leading asterisk before XX)
#   "ending in XX0000" / "ending XX0000" (OneCard wording)
_CARD_MASK = re.compile(r"\b(?:ending(?:\s+in)?\s+)?(\*?XX\d+|x\d+)\b")

# Account mask: similar shape but introduced by Acct / A/C / Account.
_ACCOUNT_MASK = re.compile(r"\b(?:Acct|A/C|Account)\s*\*?\s*(XX\d+)\b")


def normalize_whitespace(s: str) -> str:
    """Collapse runs of whitespace to single spaces, strip leading/trailing."""
    return re.sub(r"\s+", " ", s).strip()


def extract_card_mask(body: str) -> str | None:
    """Extract a card mask from an SMS body. Returns None if absent."""
    m = _CARD_MASK.search(body)
    if not m:
        return None
    raw = m.group(1)
    # IndusInd's leading asterisk is part of the formatting; strip it for the
    # extracted value, leaving "XX0000" not "*XX0000".
    return raw.lstrip("*")


def extract_account_mask(body: str) -> str | None:
    """Extract an account mask from an SMS body. Returns None if absent."""
    m = _ACCOUNT_MASK.search(body)
    return m.group(1) if m else None
