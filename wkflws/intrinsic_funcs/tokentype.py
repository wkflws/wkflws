import enum


@enum.unique
class TokenType(str, enum.Enum):
    """Describes the types of tokens found in an intrinsic function call."""

    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        return name

    # Single Character Tokens
    LEFT_PAREN = enum.auto()
    RIGHT_PAREN = enum.auto()
    COMMA = enum.auto()
    DOT = enum.auto()
    PLUS = enum.auto()
    MINUS = enum.auto()
    SLASH = enum.auto()
    STAR = enum.auto()
    # Literals
    IDENTIFIER = enum.auto()
    STRING = enum.auto()
    NUMBER = enum.auto()
    JSONPATH = enum.auto()

    EOF = enum.auto()
