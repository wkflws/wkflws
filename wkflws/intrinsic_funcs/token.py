from typing import Any

from .tokentype import TokenType


class Token:
    """Describes a piece (token) of an intrinsic function call."""

    def __init__(
        self,
        type_: TokenType,
        lexeme: str,
        literal: Any,
        offset_start: int,
        offset_end: int,
    ):
        """Create a new Token.

        Args:
            type_: The type of the token.
            lexeme: The raw text of the token defined in source code.
            literal: The literal value of the token, if there is one.
            offset_start: the offset in the source code where the lexeme begins.
            offset_end: the offset in the source code where the lexeme ends.
        """
        self.type = type_
        self.lexeme = lexeme
        self.literal = literal
        self.offset_start = offset_start
        self.offset_end = offset_end

    def __repr__(self):
        return (
            f"<Token {self.type}: {self.lexeme}: {self.literal} "
            f"(#{self.offset_start}-{self.offset_end})>"
        )
