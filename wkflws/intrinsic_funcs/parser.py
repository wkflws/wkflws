"""Parser for intrinsic functions.

expression   -> term ;
term         -> factor ( ( "-" | "+" ) factor )* ;
factor       -> unary ( ( "/" | "*" ) unary )* ;
unary        -> "-" unary | primary ;
call         -> primary ( "(" arguments? ")" | "." IDENTIFIER )* ;
arguments    -> expression ( "," expression )* ;
primary      -> NUMBER | STRING | IDENTIFIER | JSONPATH | "(" expression ")" ;
"""
from typing import List, Tuple

from . import expr as _expr
from . import stmt as _stmt
from .token import Token, TokenType


class Parser:
    """Parse tokens into an abstract syntax tree."""

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.statements: List[_stmt.Stmt] = []
        self.current: int = 0

    def match(self, token_types: Tuple[TokenType, ...]) -> bool:
        """Possibly match a token and advance the cursor.

        This method will advance the cursor only if the current token matches one of the
        provided types.

        Args:
            token_types: A tuple of token types to be matched.

        Returns:
            Whether a match was found.
        """
        for token_type in token_types:
            if self.check(token_type):
                self.advance()
                return True

        return False

    def check(self, token_type: TokenType) -> bool:
        """Check if the current token matched a specific type.

        This method does not advance the cursor.

        Args:
            token_type: The type to be matched.

        Returns:
            Whether a match was found.
        """
        if self.at_end:
            return False

        return self.peek().type == token_type

    def advance(self) -> Token:
        """Advances the cursor one token.

        Returns:
           The token before the cursor is advanced.
        """
        if not self.at_end:
            self.current += 1

        return self.previous()

    def previous(self) -> Token:
        """Provide the last token.

        Returns:
            The previous token.
        """
        # TODO: This may return the EOF token if it is called at the beginning.
        return self.tokens[self.current - 1]

    def peek(self) -> Token:
        """Provide the current token.

        Returns:
            The token for the current cusor location.
        """
        return self.tokens[self.current]

    def consume(self, token_type: TokenType, message: str):
        """Provide the current token advancing the cursor if ``token_type`` is matched.

        This method is similar to check except it will provide the token (instead of a
        bool) if it matches ``token_type`` as well as advancing the cursor. It also
        raises an error if no match was made.

        Args:
            token_type: The token type to be matched.
            msg: The error message to return if no match is found.

        Raises:
            ParseError: The current token does not match the requested type.

        Returns:
            The current token.
        """
        if self.check(token_type):
            return self.advance()

        raise ParseError(self.peek(), message)

    @property
    def at_end(self) -> bool:
        """Indicate whether all tokens have been consumed."""
        return self.peek().type == TokenType.EOF

    def parse(self) -> List[_stmt.Stmt]:
        """Begins parsing the list of tokens.

        Returns:
           The expression parsed from the current token.
        """
        while not self.at_end:
            self.statements.append(self.statement())

        return self.statements

    def statement(self) -> _stmt.Stmt:
        return self.expression_statement()

    def expression_statement(self):
        expr = self.expression()
        # normally a semicolon would be consumed here.
        return _stmt.Expression(expr)

    def expression(self) -> _expr.Expr:
        """Parse an expression.

        This is the starting point for parsing the tree. You could just call the
        upper-most expression type but using this as a pointer makes the code more
        readable.

        Raises:
            ParseError: Unable to determine the expression.

        Returns:
            The expression parsed from one or more tokens.
        """
        return self.term()

    def term(self) -> _expr.Expr:
        """Parse addition and subtraction operations falling through if necessary.

        Raises:
            ParseError: Unable to determine the expression.

        Returns:
            The expression parsed from one or more tokens.
        """
        expr = self.factor()

        while self.match((TokenType.MINUS, TokenType.PLUS)):
            operator = self.previous()
            right = self.factor()

            expr = _expr.Binary(expr, operator, right)

        return expr

    def factor(self) -> _expr.Expr:
        """Parse division and multiplication operations falling through if necessary.

        Raises:
            ParseError: Unable to determine the expression.

        Returns:
            The expression parsed from one or more tokens.
        """
        expr = self.unary()
        while self.match((TokenType.SLASH, TokenType.STAR)):
            operator = self.previous()
            right = self.unary()

            expr = _expr.Binary(expr, operator, right)

        return expr

    def unary(self) -> _expr.Expr:
        """Parse single element expressions falling through if necessary.

        Raises:
            ParseError: Unable to determine the expression.

        Returns:
            The expression parsed from one or more tokens.
        """
        if self.match((TokenType.MINUS,)):
            operator = self.previous()
            right = self.unary()
            return _expr.Unary(operator, right)

        return self.call()

    def call(self) -> _expr.Expr:
        """Parse a function call expression.

        Raises:
            ParseError: Unable to determin the expression.

        Returns:
            The evaluated result of the call.
        """
        expr = self.primary()

        while True:
            # Technically supports get_callback()()
            if self.match((TokenType.LEFT_PAREN,)):
                expr = self.finish_call(expr)
            elif self.match((TokenType.DOT,)):
                name = self.consume(
                    TokenType.IDENTIFIER, "Expected property name after '.'."
                )

                # This is a little bit of a hack to support calls that look like methods
                # when there are no classes to access methods on. Normally you'd call a
                # a `Get` expression on a `Class` to receive the property on that class.
                expr.name.lexeme += f".{name.lexeme}"  # type:ignore
                if self.match((TokenType.LEFT_PAREN,)):
                    expr = self.finish_call(expr)
            else:
                break

        return expr

    def finish_call(self, callee: _expr.Expr) -> _expr.Call:
        """Parse arguments to finish building the call expression.

        Args:
            callee: The (function/method) callee's identifier expression.

        Return:
            The call expression complete with arguments.
        """
        arguments: List[_expr.Expr] = []

        if not self.check(TokenType.RIGHT_PAREN):
            while True:
                if len(arguments) >= 254:
                    # While the number of arguments a Python (>3.7) function can accept
                    # is unlimited we shouldn't give users the option (until/if it makes
                    # sense later).
                    raise ParseError(
                        self.peek(), "Number of arguments must not exceed 254."
                    )
                arguments.append(self.expression())
                if not self.match((TokenType.COMMA,)):
                    break

        paren = self.consume(TokenType.RIGHT_PAREN, "Expected ')' after arguments.")
        return _expr.Call(callee, paren, arguments)

    def primary(self) -> _expr.Expr:
        """Parse primary expressions.

        Raises:
            ParseError: Unable to determine the expression.

        Returns:
            The expression parsed from one or more tokens.
        """
        if self.match((TokenType.NUMBER, TokenType.STRING)):
            return _expr.Literal(self.previous().literal)

        elif self.match((TokenType.LEFT_PAREN,)):
            expr = self.expression()
            self.consume(TokenType.RIGHT_PAREN, "Expected ')' after expression.")
            return _expr.Grouping(expr)

        elif self.match((TokenType.IDENTIFIER,)):
            return _expr.Variable(self.previous())

        elif self.match((TokenType.JSONPATH,)):
            return _expr.Variable(self.previous())

        # Possibly unimplemented expression type for new feature.
        raise ParseError(self.peek(), "Expected expression.")


class ParseError(Exception):
    """Represents an error when the parser encounters an unrecoverable error."""

    def __init__(self, token: Token, message: str, *args: object) -> None:
        """Construct the error.

        Args:
            token: The token the parser was on when the error occured.
            message: The error message to display.
        """
        self.token = token
        self.message = message
        super().__init__(message, *args)
