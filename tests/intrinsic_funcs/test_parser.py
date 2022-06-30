from decimal import Decimal

import pytest
from pytest_mock import MockerFixture

from wkflws.intrinsic_funcs import expr as _expr
from wkflws.intrinsic_funcs import stmt as _stmt
from wkflws.intrinsic_funcs.parser import ParseError, Parser
from wkflws.intrinsic_funcs.token import Token, TokenType

EOF_TOKEN = Token(TokenType.EOF, "", None, 101, 101)
TOKENS = [
    Token(TokenType.STRING, "'Hello, World!'", "Hello, World!", 1, 13),
    EOF_TOKEN,
]

# Mocks are deliberatly not used in expression tests to ensure that any changes which
# break the recursive nature of the parser will be raised.


def test_match():
    p = Parser(TOKENS)
    assert (
        p.match((TokenType.STRING,)) is True
    ), "Expecting string type to match first token."


def test_match__miss():
    p = Parser(TOKENS)
    assert (
        p.match((TokenType.COMMA,)) is False
    ), "Not expecting comma type to match first token."


def test_check__match():
    p = Parser(TOKENS)
    assert p.check(TokenType.STRING) is True, "Expecting string to match first token."


def test_check__no_match():
    p = Parser(TOKENS)
    assert (
        p.check(TokenType.NUMBER) is False
    ), "Not expecting number to match first token."


def test_check__at_end():
    p = Parser(TOKENS)
    p.current = 1

    assert p.check(TokenType.STRING) is False, "Expecting match miss when EOF reached."


def test_advance():
    p = Parser(TOKENS)

    assert p.advance() == TOKENS[0], "Expected first token returned."
    assert p.current == 1, "Expected counter to increment."


def test_advance__at_end():
    p = Parser(TOKENS)
    p.current = 1

    assert p.advance() == TOKENS[0], "Expected last token returned when at end."
    assert p.current == 1, "Expected counter to not increment when at end."


def test_previous():
    p = Parser(TOKENS)
    p.current = 1
    assert p.previous() == TOKENS[0], "Expecting previous token returned."


def test_peek():
    p = Parser(TOKENS)
    p.current = 1
    assert p.peek() == TOKENS[1], "Expecting 'current' token returned."


def test_consume__matched():
    p = Parser(TOKENS)
    assert (
        p.consume(TokenType.STRING, "Expected string.") == TOKENS[0]
    ), "Expecting first string token to be returned when consuming."
    assert p.current == 1, "Expecting counter to increment when consuming token."


def test_consume__no_match():
    p = Parser(TOKENS)
    msg = "Expected number."
    with pytest.raises(ParseError, match=msg):
        p.consume(TokenType.NUMBER, msg)


def test_at_end__true():
    p = Parser(TOKENS)
    p.current = 1
    assert p.at_end is True, "Expecting at_end to evaluate True when EOF token found."


def test_at_end__false():
    p = Parser(TOKENS)
    assert (
        p.at_end is False
    ), "Not expecting at_end to evaluate to True for non EOF token."


def test_parse(mocker: MockerFixture):
    # Verify parse returns a list of statements via Parser.expression. This is more of
    # an integration test to verify the entire parser works.

    p = Parser(TOKENS)
    expr = p.parse()

    assert expr == [
        _stmt.Expression(_expr.Literal("Hello, World!")),
    ], "Expecting parse to return the expression."


def test_expression():
    # This ends up falling all the way to primary. Other types are tested via other
    # tests.
    p = Parser(TOKENS)
    expr = p.expression()

    assert isinstance(
        expr, _expr.Literal
    ), "Expecting expression() to fall to primary to parse a literal string."
    assert (
        expr.value == "Hello, World!"
    ), "Expecting literal value to be `Hello, World!`."


def test_term__with_terms():
    value = Decimal("12.34")
    value2 = Decimal("10")
    value3 = Decimal("0")
    tokens = [
        Token(TokenType.NUMBER, f"{value}", value, 1, 5),
        Token(TokenType.PLUS, "+", None, 6, 7),
        Token(TokenType.NUMBER, f"{value2}", value2, 8, 10),
        Token(TokenType.MINUS, "-", None, 11, 12),
        Token(TokenType.NUMBER, f"{value3}", value3, 13, 14),
        EOF_TOKEN,
    ]

    p = Parser(tokens)

    expr = p.term()

    # expr is something like (12.34 + 10) - 0
    assert isinstance(expr, _expr.Binary)
    assert expr.operator == tokens[3]
    assert isinstance(expr.right, _expr.Literal)
    assert expr.right.value == value3

    assert isinstance(expr.left, _expr.Binary)

    assert isinstance(expr.left.left, _expr.Literal)
    assert expr.left.left.value == value

    assert isinstance(expr.left.right, _expr.Literal)
    assert expr.left.right.value == value2

    assert expr.left.operator == tokens[1]


def test_term__without_terms():
    value = Decimal("12.34")
    tokens = [
        Token(TokenType.NUMBER, f"{value}", value, 1, 5),
        # Using factor here to ensure the term() call goes through factor()
        Token(TokenType.STAR, "*", None, 6, 7),
        Token(TokenType.NUMBER, f"{value}", value, 8, 13),
        EOF_TOKEN,
    ]

    p = Parser(tokens)

    expr = p.term()

    assert isinstance(expr, _expr.Binary)
    assert expr.operator == tokens[1]
    assert isinstance(expr.left, _expr.Literal)
    assert expr.left.value == Decimal("12.34")
    assert isinstance(expr.right, _expr.Literal)
    assert expr.right.value == Decimal("12.34")


def test_factor__with_factors():
    value = Decimal("12.34")
    value2 = Decimal("10")
    value3 = Decimal("0")
    tokens = [
        Token(TokenType.NUMBER, f"{value}", value, 1, 5),
        Token(TokenType.SLASH, "/", None, 6, 7),
        Token(TokenType.NUMBER, f"{value2}", value2, 8, 10),
        Token(TokenType.STAR, "*", None, 11, 12),
        Token(TokenType.NUMBER, f"{value3}", value3, 13, 14),
        EOF_TOKEN,
    ]

    p = Parser(tokens)

    expr = p.factor()

    # expr is something like (12.34 / 10) * 0
    assert isinstance(expr, _expr.Binary)
    assert expr.operator == tokens[3]
    assert isinstance(expr.right, _expr.Literal)
    assert expr.right.value == value3

    assert isinstance(expr.left, _expr.Binary)

    assert isinstance(expr.left.left, _expr.Literal)
    assert expr.left.left.value == value

    assert isinstance(expr.left.right, _expr.Literal)
    assert expr.left.right.value == value2

    assert expr.left.operator == tokens[1]


def test_factor__without_factors():
    value = Decimal("12.34")
    tokens = [
        # Using minus here to ensure the factor call goes through unary()
        Token(TokenType.MINUS, "-", None, 1, 2),
        Token(TokenType.NUMBER, f"{value}", value, 2, 6),
        EOF_TOKEN,
    ]

    p = Parser(tokens)

    expr = p.factor()

    assert isinstance(expr, _expr.Unary)
    assert expr.operator == tokens[0]
    assert isinstance(expr.right, _expr.Literal)
    assert expr.right.value == Decimal("12.34")


def test_unary__with_minus():

    value = Decimal("12.34")
    tokens = [
        Token(TokenType.MINUS, "-", None, 1, 2),
        Token(TokenType.NUMBER, f"{value}", value, 2, 6),
        EOF_TOKEN,
    ]

    p = Parser(tokens)

    expr = p.unary()

    assert isinstance(expr, _expr.Unary)
    assert expr.operator == tokens[0]
    assert isinstance(expr.right, _expr.Literal)
    assert expr.right.value == value


def test_unary__without_minus():
    value = Decimal("12.34")
    tokens = [
        Token(TokenType.NUMBER, f"{value}", value, 1, 5),
        EOF_TOKEN,
    ]

    p = Parser(tokens)

    expr = p.unary()
    assert isinstance(expr, _expr.Literal)
    assert expr.value == value


def test_call():
    tokens = [
        Token(TokenType.IDENTIFIER, "FormatString", None, 1, 12),
        Token(TokenType.LEFT_PAREN, "(", None, 12, 13),
        Token(TokenType.STRING, "'Hello, {}'", "Hello, {}", 13, 24),
        Token(TokenType.COMMA, ",", None, 24, 25),
        Token(TokenType.STRING, "'World!'", "World!", 24, 32),
        Token(TokenType.RIGHT_PAREN, ")", None, 32, 33),
        EOF_TOKEN,
    ]
    p = Parser(tokens)

    expr = p.call()

    assert isinstance(expr, _expr.Call), "Expecting Call expression."

    assert isinstance(
        expr.callee, _expr.Variable
    ), "Expecting Callee expression to be Variable."
    assert (
        expr.callee.name.type == TokenType.IDENTIFIER
    ), "Expecting Callee type to be IDENTIFIER."
    assert (
        expr.callee.name.lexeme == "FormatString"
    ), "Expecting Call name lexeme to be function name."

    assert (
        expr.paren.type == TokenType.RIGHT_PAREN
    ), "Expecting Call.paren to be the right paren."

    assert len(expr.arguments) == 2, "Expected two arguments parsed."
    assert (
        expr.arguments[0].value == "Hello, {}"  # type:ignore # assuming literal
    ), "Unexpected first argument"
    assert (
        expr.arguments[1].value == "World!"  # type:ignore # assuming literal
    ), "Unexpected second argument"


def test_call__method():
    tokens = [
        Token(TokenType.IDENTIFIER, "States", None, 1, 12),
        Token(TokenType.DOT, ".", None, 12, 13),
        Token(TokenType.IDENTIFIER, "Format", None, 13, 18),
        Token(TokenType.LEFT_PAREN, "(", None, 18, 19),
        Token(TokenType.STRING, "'Hello, {}'", "Hello, {}", 19, 30),
        Token(TokenType.COMMA, ",", None, 30, 31),
        Token(TokenType.STRING, "'World!'", "World!", 31, 39),
        Token(TokenType.RIGHT_PAREN, ")", None, 39, 40),
        EOF_TOKEN,
    ]
    p = Parser(tokens)

    expr = p.call()

    assert isinstance(expr, _expr.Call), "Expecting Call expression."

    assert isinstance(
        expr.callee, _expr.Variable
    ), "Expecting Callee expression to be Variable."
    assert (
        expr.callee.name.type == TokenType.IDENTIFIER
    ), "Expecting Callee type to be IDENTIFIER."
    assert (
        expr.callee.name.lexeme == "States.Format"
    ), "Expecting method looking Call name lexeme to be full dot name."


def test_call__stacked():
    tokens = [
        Token(TokenType.IDENTIFIER, "FormatString", None, 1, 12),
        Token(TokenType.LEFT_PAREN, "(", None, 12, 13),
        Token(TokenType.RIGHT_PAREN, ")", None, 13, 14),
        Token(TokenType.LEFT_PAREN, "(", None, 14, 15),
        Token(TokenType.RIGHT_PAREN, ")", None, 15, 16),
        EOF_TOKEN,
    ]
    p = Parser(tokens)

    expr = p.call()

    assert isinstance(expr, _expr.Call), "Expecting Call expression."
    assert isinstance(expr.callee, _expr.Call), "Expecting nested call expression."


def test_call__multi_dot():
    tokens = [
        Token(TokenType.IDENTIFIER, "States", None, 1, 12),
        Token(TokenType.DOT, ".", None, 12, 13),
        Token(TokenType.IDENTIFIER, "Format", None, 13, 18),
        Token(TokenType.DOT, ".", None, 12, 13),
        Token(TokenType.IDENTIFIER, "Again", None, 13, 18),
        Token(TokenType.LEFT_PAREN, "(", None, 18, 19),
        Token(TokenType.RIGHT_PAREN, ")", None, 19, 20),
        EOF_TOKEN,
    ]
    p = Parser(tokens)

    expr = p.call()

    assert isinstance(expr, _expr.Call), "Expecting Call expression."
    assert isinstance(
        expr.callee, _expr.Variable
    ), "Expecting Callee expression to be Variable."
    assert (
        expr.callee.name.type == TokenType.IDENTIFIER
    ), "Expecting Callee type to be IDENTIFIER."
    assert (
        expr.callee.name.lexeme == "States.Format.Again"
    ), "Expecting method looking Call name lexeme to be full dot name."


def test_call__max_arguments():
    tokens = [
        Token(TokenType.IDENTIFIER, "FormatString", None, 1, 12),
        Token(TokenType.LEFT_PAREN, "(", None, 12, 13),
    ]

    begin = 13
    for i in range(0, 255):
        string_end = begin + 6  # end of Hello! string
        tokens.append(Token(TokenType.STRING, "'Hello!'", "Hello!", begin, string_end))
        begin = string_end + 1  # end at comma, begin of next Hello
        tokens.append(Token(TokenType.COMMA, ",", None, string_end, begin))

    tokens.pop()  # remove trailing comma

    tokens.append(Token(TokenType.RIGHT_PAREN, ")", None, begin - 1, begin))
    tokens.append(EOF_TOKEN)

    p = Parser(tokens)

    with pytest.raises(ParseError, match="Number of arguments must not exceed 254."):
        p.call()


def test_primary__number():
    value = Decimal("12.34")
    p = Parser(
        [
            Token(TokenType.NUMBER, f"{value}", value, 1, 5),
            EOF_TOKEN,
        ]
    )

    expr = p.primary()

    assert isinstance(expr, _expr.Literal)
    assert expr.value == value


def test_primary__string():
    value = "Hello, World!"
    p = Parser(
        [
            Token(TokenType.STRING, f"'{value}'", value, 1, 13),
            EOF_TOKEN,
        ]
    )

    expr = p.primary()

    assert isinstance(expr, _expr.Literal)
    assert expr.value == value


def test_primary__group():
    value = "Hello, World!"
    p = Parser(
        [
            Token(TokenType.LEFT_PAREN, "(", None, 1, 2),
            Token(TokenType.STRING, f"'{value}'", value, 2, 15),
            Token(TokenType.RIGHT_PAREN, ")", None, 16, 17),
            EOF_TOKEN,
        ]
    )

    expr = p.primary()

    assert isinstance(expr, _expr.Grouping)
    assert isinstance(expr.expression, _expr.Literal)
    assert expr.expression.value == value


def test_primary__identifier():
    value = "my_variable"
    p = Parser(
        [
            Token(TokenType.IDENTIFIER, value, None, 1, 11),
            EOF_TOKEN,
        ]
    )
    expr = p.primary()

    assert isinstance(expr, _expr.Variable)
    assert isinstance(expr.name, Token)
    assert expr.name.type == TokenType.IDENTIFIER


def test_primary__jsonpath():
    value = "$.some.json_path[0]"
    p = Parser(
        [
            Token(TokenType.JSONPATH, value, None, 1, 19),
            EOF_TOKEN,
        ]
    )
    expr = p.primary()

    assert isinstance(expr, _expr.Variable)
    assert isinstance(expr.name, Token)
    assert expr.name.type == TokenType.JSONPATH


def test_primary__error():
    # This shouldn't happen but verify that an exception is thrown incase it does.
    p = Parser(
        [
            EOF_TOKEN,
        ]
    )

    with pytest.raises(ParseError):
        p.primary()
