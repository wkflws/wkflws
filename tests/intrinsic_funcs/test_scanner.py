from decimal import Decimal

import pytest
from pytest_mock import MockerFixture

from wkflws.intrinsic_funcs.scanner import Scanner, TokenType

# Scanner._print_cursor_location = True


def test_scan(mocker: MockerFixture):
    scan_token_mock = mocker.patch(
        "wkflws.intrinsic_funcs.scanner.Scanner.scan_token",
    )
    mocker.patch(
        "wkflws.intrinsic_funcs.scanner.Scanner.at_end",
        new_callable=mocker.PropertyMock,
        side_effect=[False, False, False, True],
    )
    s = Scanner('"Hello, World!"')

    tokens = s.scan()

    assert scan_token_mock.call_count == 3, "Expected scan token to be called 3 times"

    # There will only be 1 token because we've made dummy calls to scan_token.
    assert len(tokens) == 1, "Expected one token."
    assert tokens is s.tokens, "Expected return value to be the internal tokens list."
    assert tokens[-1].type == TokenType.EOF, "Expected last token to be EOF."


def test_scan_token__LEFT_PAREN():
    source = "("
    s = Scanner(source)
    s.scan_token()

    assert len(s.tokens) == 1, "Expecting one token."

    token = s.tokens[0]
    assert token.type == TokenType.LEFT_PAREN, "Expecting token type of LEFT_PAREN"
    assert token.literal is None, "Unexpected literal value for LEFT_PAREN"
    assert token.lexeme == "(", "Unexpected lexeme evaluated to LEFT_PAREN"


def test_scan_token__RIGHT_PAREN():
    source = ")"
    s = Scanner(source)
    s.scan_token()

    assert len(s.tokens) == 1, "Expecting one token."

    token = s.tokens[0]
    assert token.type == TokenType.RIGHT_PAREN, "Expecting token type of RIGHT_PAREN"
    assert token.literal is None, "Unexpected literal value for RIGHT_PAREN"
    assert token.lexeme == ")", "Unexpected lexeme evaluated to RIGHT_PAREN"


def test_scan_token__COMMA():
    source = ","
    s = Scanner(source)
    s.scan_token()

    assert len(s.tokens) == 1, "Expecting one token."

    token = s.tokens[0]
    assert token.type == TokenType.COMMA, "Expecting token type of COMMA"
    assert token.literal is None, "Unexpected literal value for COMMA"
    assert token.lexeme == ",", "Unexpected lexeme evaluated to COMMA"


def test_scan_token__DOT():
    source = "."
    s = Scanner(source)
    s.scan_token()

    assert len(s.tokens) == 1, "Expecting one token."

    token = s.tokens[0]
    assert token.type == TokenType.DOT, "Expecting token type of DOT"
    assert token.literal is None, "Unexpected literal value for DOT"
    assert token.lexeme == ".", "Unexpected lexeme evaluated to DOT"


def test_scan_token__MINUS():
    source = "-"
    s = Scanner(source)
    s.scan_token()

    assert len(s.tokens) == 1, "Expecting one token."

    token = s.tokens[0]
    assert token.type == TokenType.MINUS, "Expecting token type of MINUS"
    assert token.literal is None, "Unexpected literal value for MINUS"
    assert token.lexeme == "-", "Unexpected lexeme evaluated to MINUS"


def test_scan_token__PLUS():
    source = "+"
    s = Scanner(source)
    s.scan_token()

    assert len(s.tokens) == 1, "Expecting one token."

    token = s.tokens[0]
    assert token.type == TokenType.PLUS, "Expecting token type of PLUS"
    assert token.literal is None, "Unexpected literal value for PLUS"
    assert token.lexeme == "+", "Unexpected lexeme evaluated to PLUS"


def test_scan_token__SLASH():
    source = "/"
    s = Scanner(source)
    s.scan_token()

    assert len(s.tokens) == 1, "Expecting one token."

    token = s.tokens[0]
    assert token.type == TokenType.SLASH, "Expecting token type of SLASH"
    assert token.literal is None, "Unexpected literal value for SLASH"
    assert token.lexeme == "/", "Unexpected lexeme evaluated to SLASH"


def test_scan_token__STAR():
    source = "*"
    s = Scanner(source)
    s.scan_token()

    assert len(s.tokens) == 1, "Expecting one token."

    token = s.tokens[0]
    assert token.type == TokenType.STAR, "Expecting token type of STAR"
    assert token.literal is None, "Unexpected literal value for STAR"
    assert token.lexeme == "*", "Unexpected lexeme evaluated to STAR"


def test_scan_token__QUOTE(mocker: MockerFixture):
    process_string_mock = mocker.patch(
        "wkflws.intrinsic_funcs.scanner.Scanner.process_string"
    )
    source = "'"
    s = Scanner(source)
    s.scan_token()

    assert (
        len(s.tokens) == 0
    ), "Expecting no tokens. Should be handled by process_string."

    process_string_mock.assert_called_once()


def test_scan_token__DOLLARSIGN(mocker: MockerFixture):
    process_jsonpath_mock = mocker.patch(
        "wkflws.intrinsic_funcs.scanner.Scanner.process_jsonpath"
    )
    source = "$"
    s = Scanner(source)
    s.scan_token()

    assert (
        len(s.tokens) == 0
    ), "Expecting no tokens. Should be handled by process_jsonpath."

    process_jsonpath_mock.assert_called_once()


def test_scan_token__SPACE():
    source = " "
    s = Scanner(source)
    s.scan_token()

    assert len(s.tokens) == 0, "Expecting no tokens for space."


def test_scan_token__number(mocker: MockerFixture):
    process_number_mock = mocker.patch(
        "wkflws.intrinsic_funcs.scanner.Scanner.process_number"
    )
    source = "4"
    s = Scanner(source)
    s.scan_token()

    assert (
        len(s.tokens) == 0
    ), "Expecting no tokens. Should be handled by process_number."

    process_number_mock.assert_called_once()


def test_scan_token__identifier(mocker: MockerFixture):
    process_identifier_mock = mocker.patch(
        "wkflws.intrinsic_funcs.scanner.Scanner.process_identifier"
    )
    source = "a"
    s = Scanner(source)
    s.scan_token()

    assert (
        len(s.tokens) == 0
    ), "Expecting no tokens. Should be handled by process_identifier."

    process_identifier_mock.assert_called_once()


def test_scan_token__unrecognized_char():
    source = "~"
    s = Scanner(source)
    with pytest.raises(Exception):
        s.scan_token()

    assert len(s.tokens) == 0, "Expecting no tokens."


def test_process_string():
    # Test processing a string
    source = "'Hello, World!'"
    s = Scanner(source)

    # Advance the cursor to mimic scan_token consuming the first quotation mark.
    s.source.read(1)

    s.process_string()

    assert len(s.tokens) == 1, "Expecting one token."

    token = s.tokens[0]
    assert token.type == TokenType.STRING, "Expecting token type of STRING."
    assert token.literal == "Hello, World!", "Token literal doesn't match expected."
    assert token.lexeme == "'Hello, World!'", "Token lexeme doesn't match expected."


def test_process_string__escape_apostrophe():
    # Test processing a string with an escaped apostrophe
    source = "'I\\'m new here.'"
    s = Scanner(source)

    # Advance the cursor to mimic scan_token consuming the first quotation mark.
    s.source.read(1)

    s.process_string()

    assert len(s.tokens) == 1, "Expecting one token."

    token = s.tokens[0]
    assert token.type == TokenType.STRING, "Expecting token type of STRING."
    assert token.literal == "I'm new here.", "Token literal doesn't match expected."
    assert token.lexeme == "'I\\'m new here.'", "Token lexeme doesn't match expected."


def test_process_string__unicode():
    # Test processing a unicode string
    source = "'ハロー・ワールド'"
    s = Scanner(source)

    # Advance the cursor to mimic scan_token consuming the first quotation mark.
    s.source.read(1)

    s.process_string()

    assert len(s.tokens) == 1, "Expecting one string token."

    token = s.tokens[0]
    assert token.type == TokenType.STRING, "Expecting token type of STRING."
    assert token.literal == "ハロー・ワールド", "Token literal doesn't match expected."
    assert token.lexeme == "'ハロー・ワールド'", "Token lexeme doesn't match expected."


def test_process_string__unterminated():
    source = '"Unterminated string'
    s = Scanner(source)

    # Advance the cursor to mimic scan_token consuming the first quotation mark.
    s.source.read(1)

    with pytest.raises(Exception):
        s.process_string()

    assert len(s.tokens) == 0, "Expecting no tokens."


def test_process_jsonpath():
    # Verify JSON path variables are extracted when they are for the input.
    rfc_examples = (
        "$.store.book[*].author",  # the authors of all books in the store
        "$..author",  # all authors
        "$.author['first-name']",  # author first name. support for -
        "$.store.*",  # all things in store, which are some books and a red bicycle
        "$.store..price",  # the prices of everything in the store
        "$..book[2]",  # the third book
        "$..book[-1]",  # the last book in order
        "$..book[0,1]",  # the first two books
        "$..book[:2]",  # the first two books, another way
        "$..book[?(@.isbn)]",  # filter all books with isbn number
        "$['store']['book'][0]['title']",  # selectors instead of dot notation
        '$["store"]["book"][0]["title"]',  # quotes instead of single quotes
    )
    for ex in rfc_examples:
        s = Scanner(ex)
        # Advance the cursor to mimic scan_token consuming the first $
        s.source.read(1)

        try:
            s.process_jsonpath()
        except Exception as e:
            # display the jsonpath currently being processed on exception.
            raise e.__class__(f"{ex}: {e}")

        assert len(s.tokens) == 1, "Expecting one token."
        token = s.tokens[0]

        assert token.type == TokenType.JSONPATH, "Expecting token type of JSONPATH."
        assert token.lexeme == ex, "Unexpected JSONPATH lexeme extracted."


def test_process_jsonpath__move_back_after_break():
    # Verify process_jsonpath evaluates to the proper value after it encounters an
    # unsupported character.

    # this looks a little weird but it would be total price minus 44
    jpath = "$.total_price-44"

    s = Scanner(jpath)
    s.source.read(1)

    s.process_jsonpath()

    assert len(s.tokens) == 1, "Expecting one token."
    token = s.tokens[0]

    assert token.type == TokenType.JSONPATH, "Expecting token type of JSONPATH."
    assert token.lexeme == jpath.split("-")[0], "Unexpected JSONPATH lexeme extracted."


def test_process_jsonpath__context():
    # Verify JSON path variables are extracted when they are for the context.
    rfc_examples = (
        "$$.store.book[*].author",  # the authors of all books in the store
        "$$..book[:2]",  # the first two books, another way
        "$$..book[?(@.isbn)]",  # filter all books with isbn number
    )
    for ex in rfc_examples:
        s = Scanner(ex)
        # Advance the cursor to mimic scan_token consuming the first $
        s.source.read(1)

        try:
            s.process_jsonpath()
        except Exception as e:
            # display the jsonpath currently being processed on exception.
            raise e.__class__(f"{ex}: {e}")

        assert len(s.tokens) == 1, "Expecting one token."
        token = s.tokens[0]

        assert token.type == TokenType.JSONPATH, "Expecting token type of JSONPATH."
        assert token.lexeme == ex, "Unexpected JSONPATH lexeme extracted."


def test_process_jsonpath__descendant_selector_with_alpha():
    # Verify decendant-selector with index-selector branch
    ex = "$..['author']"

    s = Scanner(ex)
    # Advance the cursor to mimic scan_token consuming the first $
    s.advance()

    s.process_jsonpath()

    assert len(s.tokens) == 1, "Expecting one token."
    token = s.tokens[0]

    assert token.type == TokenType.JSONPATH, "Expecting token type of JSONPATH."
    assert token.lexeme == ex, "Unexpected JSONPATH lexeme extracted."


def test_process_jsonpath__dot_selector_bad_member_name():
    # Verify error when an invalid member name follows a dot selector
    s = Scanner("$.[*]")
    s.advance()
    with pytest.raises(Exception, match="Member name must begin"):
        s.process_jsonpath()


def test_process_jsonpath__invalid_dot_wild_selector():
    # Verify dot-wild-selector is exactly [*]. anything else is invalid
    s = Scanner("$.book[*z]")
    s.advance()
    with pytest.raises(Exception, match="Wildcard selector must"):
        s.process_jsonpath()


def test_process_jsonpath__unterminated_selector():
    # Verify selectors must be terminated
    s = Scanner("$.author[1")
    s.advance()
    with pytest.raises(Exception, match="Unterminated selector"):
        s.process_jsonpath()


def test_process_jsonpath__space():
    # Verify whitespace. I don't know why this is valid, but it is.
    s = Scanner("$ ")
    s.advance()

    s.process_jsonpath()

    assert len(s.tokens) == 1, "Expecting one token."
    token = s.tokens[0]

    assert token.type == TokenType.JSONPATH, "Expecting token type of JSONPATH."
    assert token.lexeme == "$ ", "Expected JSONPATH scanner to support space."


def test_process_jsonpath__tab():
    # Verify whitespace. I don't know why this is valid, but it is.
    s = Scanner("$\t")
    s.advance()

    s.process_jsonpath()

    assert len(s.tokens) == 1, "Expecting one token."
    token = s.tokens[0]

    assert token.type == TokenType.JSONPATH, "Expecting token type of JSONPATH."
    assert token.lexeme == "$\t", "Expected JSONPATH scanner to support tab."


def test_process_jsonpath__newline():
    # Verify whitespace. I don't know why this is valid, but it is.
    s = Scanner("$\n")
    s.advance()

    s.process_jsonpath()

    assert len(s.tokens) == 1, "Expecting one token."
    token = s.tokens[0]

    assert token.type == TokenType.JSONPATH, "Expecting token type of JSONPATH."
    assert token.lexeme == "$\n", "Expected JSONPATH scanner to support newline."


def test_process_jsonpath__carriage_return():
    # Verify whitespace. I don't know why this is valid, but it is.
    s = Scanner("$\r")
    s.advance()

    s.process_jsonpath()

    assert len(s.tokens) == 1, "Expecting one token."
    token = s.tokens[0]

    assert token.type == TokenType.JSONPATH, "Expecting token type of JSONPATH."
    assert (
        token.lexeme == "$\r"
    ), "Expected JSONPATH scanner to support carriage return."


def test_process_number__integer():
    # Test processing a number
    source = "31337"
    s = Scanner(source)

    s.process_number()

    assert len(s.tokens) == 1, "Expecting one token."

    token = s.tokens[0]
    assert token.type == TokenType.NUMBER, "Expecting token type of NUMBER."
    assert token.literal == Decimal(source)
    assert token.lexeme == source


def test_process_number__decimal():
    # Test processing a number when it has decimal places.
    source = "31.337"
    s = Scanner(source)

    s.process_number()

    assert len(s.tokens) == 1, "Expecting one token."

    token = s.tokens[0]
    assert token.type == TokenType.NUMBER, "Expecting token type of NUMBER."
    assert token.literal == Decimal(source)
    assert token.lexeme == source


def test_identifier():
    # Test processing an identifier
    source = "my_special_variable"
    s = Scanner(source)

    s.process_identifier()

    assert len(s.tokens) == 1, "Expecting one token."
    token = s.tokens[0]
    assert token.lexeme == source, "Unexpected lexeme for identifier."
    assert token.type == TokenType.IDENTIFIER, "Unexpected token type for IDENTIFIER."


def test_add_token():
    # Validate add_token
    s = Scanner("")

    assert len(s.tokens) == 0, "Expecting no tokens to be added on initialization."

    # Defaults
    s.add_token(TokenType.COMMA)
    assert len(s.tokens) == 1, "Expecting one token to be added."

    s.add_token(TokenType.IDENTIFIER, "my_special_variable")
    assert len(s.tokens) == 2, "Expecting a second token to be added."


def test_current():
    # verify current property returns the current location of the cursor.
    source = "12345"
    s = Scanner(source)
    char_loc = 3
    r = ""
    for _ in range(0, 3):
        r = s.source.read(1)
        print(r)

    assert (
        r == source[char_loc - 1]
    ), f"Expecting last read char to be {source[char_loc - 1]}."

    # cursor at next character
    assert s.current == char_loc, f"Expecting cursor location to be at {char_loc}."


def test_at_end():
    source = "the last character is q"
    s = Scanner(source)

    r = s.source.read(len(source) - 1)
    assert r[-1] == source[-2], "Expecting to have read the second to last character."

    assert s.at_end is False, "Expecting source to not be at end yet."

    assert s.source.read(1) == source[-1], "Expecting to have read the last character"

    assert s.at_end is True, "Expecting source to be at end."


def test_peek__simple():
    source = 'States.Format("Hello, {}", "World!")'
    s = Scanner(source)

    # Advance cursor to set up the tests.
    assert s.source.read(1) == "S", "First character not expected."
    assert s.source.read(1) == "t", "Second character not expected."

    assert s.peek() == source[2], f"Expected third character to be {source[2]}."
    assert s.peek(count=4) == source[5], f"Expected sixth character to be {source[5]}."
    assert (
        s.peek(count=10) == source[11]
    ), f"Expected twelfth character to be {source[11]}."


def test_peek__backward():
    source = 'States.Format("Hello, {}", "World!")'
    s = Scanner(source)

    with pytest.raises(ValueError, match="Peeking backward"):
        s.peek(count=-1)


def test_peek__past_end_of_string():
    # Test that peek returns to the current position after peeking too far forward.
    source = 'States.Format("Hello, {}", "World!")'
    s = Scanner(source)

    # Advance to near the end
    while True:
        c = s.source.read(1)
        assert c != "", "Advanced too far during peek test."

        if c == "!":
            break

    exclaim_char_pos = s.source.tell()

    # Peek past the end of teh string
    assert (
        s.peek(count=10) == ""
    ), "Expected empty string when peeking past end of source."

    assert (
        s.source.tell() == exclaim_char_pos
    ), f"Expected to be at pos {exclaim_char_pos} after peeking past end of source."
    assert (
        s.peek() == '"'
    ), "Expected to be at ! character after peeking past end of source."


def test_peek__at_end_of_string():
    # Test peek stays at the last character when peeking to the end of the string.
    source = 'States.Format("Hello, {}", "World!")'
    s = Scanner(source)

    # Advance to the final character
    # Advance to near the end
    while True:
        c = s.source.read(1)
        assert c != "", "Advanced too far during peek test."

        if c == ")":
            break

    last_char_pos = s.source.tell()

    assert s.peek() == "", "Expected to be at end of source."
    assert (
        s.source.tell() == last_char_pos
    ), "Expected to be on last character after peeking to end of source."


def test_advance():
    # Test advance call advances the cursor.
    source = "Hello, World!"
    s = Scanner(source)

    assert (
        s.advance() == source[0]
    ), "Expecting first character returned on call to advanced."
    assert s.source.tell() == 1, "Expecting cursor to advance to first character."
    assert (
        s.advance() == source[1]
    ), "Expecting second character returned on call to advanced."
    assert s.source.tell() == 2, "Expecting cursor to advance to second character."
    assert (
        s.advance() == source[2]
    ), "Expecting third character returned on call to advanced."
    assert s.source.tell() == 3, "Expecting cursor to advance to third character."


def test_advance__print_cursor_loc(mocker: MockerFixture):
    # Test advance call advances the cursor.
    source = "Hello, World!"

    mocker.patch(
        "wkflws.intrinsic_funcs.scanner.Scanner._print_cursor_location",
        new_callable=mocker.PropertyMock,
        return_value=True,
    )
    print_mock = mocker.patch("builtins.print")

    s = Scanner(source)

    s.advance()
    assert (
        print_mock.mock_calls[0].args[0] == source
    ), "Expecting source to be printed when _print_cursor_loc enabled."
    assert (
        print_mock.mock_calls[1].args[0] == "^"
    ), "Expecting cursor indicator on first char."
    print_mock.reset_mock()

    s.advance()
    assert (
        print_mock.mock_calls[0].args[0] == source
    ), "Expecting source to be printed when _print_cursor_loc enabled."
    assert (
        print_mock.mock_calls[1].args[0] == " ^"
    ), "Expecting cursor indicator on second char on second advance call."


def test_match():
    # Test cursor advances when a match is found.
    source = "Hello, World!"
    s = Scanner(source)

    assert s.match(source[0]) is True, "Expecting match to be found."
    assert s.source.tell() == 1, "Expecting cursor to advance when match found."


def test_match__miss():
    # Test cursor does not advances when a match is not found.
    source = "Hello, World!"
    s = Scanner(source)

    assert s.match("7") is False, "Expecting match miss."
    assert s.source.tell() == 0, "Expecting cursor to advance when match found."


def test_is_digit():
    # Verify all digits are detected
    for i in range(0, 10):
        assert (
            Scanner.is_digit(str(i)) is True
        ), f"Expecting {i} to be detected as a digit."


def test_is_digit__false():
    # Verify all letters are not evaluated as digits
    for i in range(0, 48):
        assert (
            Scanner.is_digit(chr(i)) is False
        ), f"Expecting {chr(i)} to fail is_digit test."

    for i in range(65, 91):  # A-Z
        assert (
            Scanner.is_digit(chr(i)) is False
        ), f"Expecting {chr(i)} to fail is_digit test."

    for i in range(97, 123):  # a-z
        assert (
            Scanner.is_digit(chr(i)) is False
        ), f"Expecting {chr(i)} to fail is_digit test."

    assert Scanner.is_digit("_") is False, "Expecting _ to fail is_digit test."


def test_is_alpha():
    # Verify all letters are detected.
    for i in range(65, 91):  # A-Z
        assert (
            Scanner.is_alpha(chr(i)) is True
        ), f"Expecting {chr(i)} to be detected as a letter."

    for i in range(97, 123):  # a-z
        assert (
            Scanner.is_alpha(chr(i)) is True
        ), f"Expecting {chr(i)} to be detected as a letter."

    assert Scanner.is_alpha("_") is True, "Expecting _ pass is_alpha test."


def test_is_alpha__false():
    # Verify digits are note detected.
    for i in range(0, 10):
        assert (
            Scanner.is_alpha(str(i)) is False
        ), f"Expecting {i} to fail is_alpha test."

    # Verify these random ascii symbols aren't detected.
    for i in range(0, 48):
        assert (
            Scanner.is_alpha(chr(i)) is False
        ), f"Expecting {chr(i)} to fail is_alpha test."


def test_is_alphanumeric(mocker: MockerFixture):
    is_alpha_mock = mocker.patch(
        "wkflws.intrinsic_funcs.scanner.Scanner.is_alpha", return_value=False
    )
    is_digit_mock = mocker.patch(
        "wkflws.intrinsic_funcs.scanner.Scanner.is_digit", return_value=False
    )

    # Note: It doesn't actually matter what is passed in because the return values are
    # mocked but so it makese sense here is a non-alphanumeric character.
    assert Scanner.is_alphanumeric("*") is False, "Expecting return value to be False."

    is_alpha_mock.assert_called_once_with("*")
    is_digit_mock.assert_called_once_with("*")


def test_substr():
    source = "oOo Hello oOo"
    s = Scanner(source)

    # Advance the cursor one position to validate it comes back after extracting the
    # string.
    s.source.read(1)

    assert s.substr(4, 5) == source[4:9], "Expecting {source[4:9]} to be extracted."

    assert (
        s.source.tell() == 1
    ), "Expecting cursor to be moved back to the original offset."
