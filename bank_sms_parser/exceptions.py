"""Exception types raised during SMS parsing."""


class ParseError(Exception):
    """Raised when an SMS body cannot be parsed despite matching the expected shape."""


class ParserStubError(NotImplementedError):
    """Raised by intentional parser stubs that are waiting for a sample SMS."""


class UnsupportedSmsTypeError(Exception):
    """Raised when the given bank identifier has no registered parser."""
