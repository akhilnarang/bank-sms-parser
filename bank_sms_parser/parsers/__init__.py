"""Bank parser registry. Populated as per-bank parsers are added."""

PARSERS: dict[str, type] = {}

__all__ = ["PARSERS"]
