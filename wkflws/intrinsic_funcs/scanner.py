from decimal import Decimal
from io import StringIO
from typing import Any, List, Optional

from .token import Token
from .tokentype import TokenType


class Scanner:
    """Scanner for intrinsic functions.

    This class will scan and convert intrinsic functions into tokens that can be parsed.
    """

    #: Setting this to True will print 2 additional lines showing the cursor location
    #: on each call to advance()
    _print_cursor_location = False

    def __init__(self, source: str):
        self._source = source
        self.source = StringIO(source)
        self.tokens: List[Token] = []

        # Tracks the start of the current lexeme
        self.start = 0

    def scan(self) -> List[Token]:
        """Scan the entire source creating a list of tokens.

        Return:
            The list of tokens created.
        """
        while not self.at_end:
            self.start = self.current

            self.scan_token()

        self.tokens.append(Token(TokenType.EOF, "", None, self.current, self.current))
        return self.tokens

    def scan_token(self):
        """Process the next character to create a token adding it to the list."""
        c = self.advance()

        match c:
            case "(":
                self.add_token(TokenType.LEFT_PAREN)
            case ")":
                self.add_token(TokenType.RIGHT_PAREN)
            case ",":
                self.add_token(TokenType.COMMA)
            case ".":
                self.add_token(TokenType.DOT)
            case "-":
                self.add_token(TokenType.MINUS)
            case "+":
                self.add_token(TokenType.PLUS)
            case "/":
                self.add_token(TokenType.SLASH)
            case "*":
                self.add_token(TokenType.STAR)
            case "'":
                self.process_string()
            case "$":
                self.process_jsonpath()
            case " ":
                pass
            case _:
                if self.is_digit(c):
                    self.process_number()
                elif self.is_alpha(c):
                    self.process_identifier()
                else:
                    # TODO: Make this a real exception
                    raise Exception(f"Unrecognized character {c} @ {self.current}")

    def process_string(self):
        """Process an entire string adding it to the token list."""
        while self.peek() != "'":
            self.advance()
            if self.peek() == "\\" and self.peek(count=2) == "'":
                # Skip an escaped apostrophe
                self.advance()
                self.advance()

            if self.at_end:
                raise Exception(f"Unterminated string at {self.start}")

        # Cursor is currently on the closing apostrophy.

        # extract the value between the two apostrophies.
        value = self.substr((self.start + 1), (self.current - 1) - self.start)

        # Replace escaped apostrophies with an apostrophe so it is what the user
        # intended.
        value = value.replace("\\'", "'")

        # consume the closing apostrophy.
        # This is done after the string literal read and before the advance to ensure
        # the lexeme and literal values are consistent.
        #
        # current_pos is at the closing apostrophy so `value` reads until just before it
        # (hence the `- 1`), then we advance so when the add_token method substr's
        # the text it includes the closing apostrophy for the entire lexeme.
        self.advance()

        self.add_token(TokenType.STRING, value)

    def process_jsonpath(self):
        """Process a JSON Path variable."""
        next_char = self.peek()

        if next_char == "$":
            # This is a JSON Path variable meant to search the context JSON string,
            # rather than the input from the previous step.
            self.advance()  # consume the second $

        # json-path = root-selector *(S (dot-selector /
        #                       dot-wild-selector     /
        #                       index-selector        /
        #                       index-wild-selector   /
        #                       list-selector         /
        #                       slice-selector        /
        #                       descendant-selector   /
        #                       filter-selector))
        while True:
            next_char = self.advance()

            match next_char:
                case ".":  # dot-selector
                    dot_next_char = self.peek()
                    if dot_next_char == "*":  # dot-wild-selector
                        self.advance()
                        continue
                    elif dot_next_char == ".":  # descendant-selector
                        self.advance()  # consume the 2nd dot

                        # Either dot-member-name, or index selectors follow.
                        if not self.is_alpha(self.peek()):
                            # Possibly an index-selector
                            continue

                    # This section is implemented exactly as defined in the spec because
                    # there seems to be some confusion with online jsonpath evaluators
                    # accepting things like $.first-name when they probably shouldn't.

                    # dot-member-name = name-first *name-char
                    # name-first      =
                    #                   ALPHA /
                    #                   "_"   /       ; _
                    #                   %x80-10FFFF   ; any non-ASCII Unicode character
                    # name-char = DIGIT / name-first
                    #
                    # DIGIT           =  %x30-39              ; 0-9
                    # ALPHA           =  %x41-5A / %x61-7A    ; A-Z / a-z
                    #
                    # Member names containing characters other than allowed by
                    # dot-selector -- such as space ` , minus -, or dot . characters --
                    # MUST NOT be used with the dot-selector. (Such member names can be
                    # addressed by the index-selector` instead.)

                    name_first = ord(self.advance())
                    if not (
                        (name_first >= 0x41 and name_first <= 0x5A)
                        or (name_first >= 0x61 and name_first <= 0x7A)
                        or name_first == ord("_")
                        or (name_first >= 0x80 and name_first <= 0x10FFFF)
                    ):
                        # "A dot selector starts with a dot . followed by an object's
                        # member name."
                        raise Exception(
                            "Member name must begin a letter or underscore."
                        )

                    name_char = ord(self.peek())
                    while (
                        (name_char >= 0x41 and name_char <= 0x5A)
                        or (name_char >= 0x61 and name_char <= 0x7A)
                        or name_char == ord("_")
                        or (name_char >= 0x80 and name_char <= 0x10FFFF)
                        or (name_char >= 0x30 and name_char <= 0x39)
                    ):
                        self.advance()
                        next_name_char = self.peek()
                        if next_name_char == "":  # EOF
                            break
                        name_char = ord(self.peek())

                case "[":  # index-selector
                    if self.peek() == "*":  # index-wild-selector
                        self.advance()
                        # An index wild card selector MUST be [*] and behaves
                        # identically to the dot-wild-selector
                        if self.advance() != "]":
                            raise Exception("Wildcard selector must be '[*]'.")
                        continue
                    # Also list-selector, slice-selector, filter-selector

                    # Naively consume all characters between the brackets. For now, if
                    # it's invalid the error will occur when interpreting the value.
                    while self.advance() != "]":
                        if self.at_end:
                            raise Exception(
                                f"Unterminated selector at {self.start}. Expected ']'"
                            )
                # S is "optional blank space" defined in section-3.5.6
                case " ":
                    self.advance()
                case "\t":
                    self.advance()
                case "\n":
                    self.advance()
                case "\r":
                    self.advance()
                case _:
                    # We've consumed the previous unmatched character so move the cursor
                    # back one and let the normal scanner take care of it.
                    if next_char != "":
                        # Moving back at EOF will result in rereading a valid character.
                        self.source.seek(self.current - 1)
                    break

        value = self.substr(self.start, self.current)

        self.add_token(TokenType.JSONPATH)

    def process_number(self):
        """Process a number value adding it to the token list."""
        # Store the value of peek in the next_char variable to save 1 call to peek when
        # evaluating that the number ends with a space.
        next_char = self.peek()
        while self.is_digit(next_char):
            self.advance()
            next_char = self.peek()

        if next_char == "." and self.is_digit(self.peek(count=2)):
            # e.g. not a method call (although unsupported)
            self.advance()  # Consume the dot

            next_char = self.peek()
            # Consume the rest of the number if it has decimals
            while self.is_digit(next_char):
                self.advance()
                next_char = self.peek()

        value = self.substr(self.start, self.current - self.start)
        self.add_token(TokenType.NUMBER, Decimal(value))

    def process_identifier(self):
        """Process an identifier adding it to the token list."""
        # Note: an identifier must start with a letter. This is enforced by scan_token.
        while self.is_alphanumeric(self.peek()):
            self.advance()

        self.add_token(TokenType.IDENTIFIER)

    def add_token(self, token_type: TokenType, literal: Optional[Any] = None):
        """Add the provided :class:`TokenType` to the list of tokens.

        Args:
            token_type: The type of token to add.
            literal: The value for literals. e.g. the string or number value or
                identifier.
        """
        # Extract the lexeme from the source code.
        text = self.substr(self.start, self.current - self.start)

        self.tokens.append(Token(token_type, text, literal, self.start, self.current))

    @property
    def current(self) -> int:
        """Return current position in the source code."""
        return self.source.tell()

    @property
    def at_end(self) -> bool:
        """Indicate if the scanner has reached the end of the source code."""
        return self.peek() == ""

    def peek(self, *, count: int = 1) -> str:
        """Lookahead at the ``count``th character without advancing the position.

        Args:
            count: The number of characters to read ahead.

        Returns:
            The character at position ``count``.
        """
        if count < 1:
            raise ValueError("Peeking backward is unsupported.")

        next_char = ""
        for i in range(1, count + 1):
            next_char = self.source.read(1)
            if next_char == "":
                # We've reached the end of the StringIO. All subsequent reads will
                # return an empty string.
                # Subtracts 1 for EOF iteration.
                self.source.seek(self.source.tell() - (i - 1))
                return next_char
        self.source.seek(self.source.tell() - count)
        return next_char

    def advance(self) -> str:
        """Consume and return the next character.

        Returns:
            The new character.
        """
        s = self.source.read(1)

        if self._print_cursor_location:
            print(self._source)
            print(f"{' '*(self.current-1)}^")

        return s

    def match(self, char: str) -> bool:
        """If the next character matches ``char`` consume it.

        Args:
            char: The desired character to match

        Returns:
            Whether a match was found.
        """
        if not self.at_end and self.peek() == char:
            self.advance()
            return True

        return False

    @staticmethod
    def is_digit(char: str) -> bool:
        """Check if the provided character is a digit.

        Args:
            char: The character to evaluate.

        Returns:
            ``True`` if the provided char is a number otherwise ``False``
        """
        # Note: if unicode numbers need to be supported, you can change this function to
        # import unicodedata
        # try:
        #     unicodedata.decimal(char)  # e.g. 四
        #     return True
        # except (ValueError, TypeError):
        #    # TypeError for string not char; ValueError for non-number
        #    pass
        # return False
        try:
            ascii_code = ord(char)
        except TypeError:
            # String passed instead of single char
            return False

        return ascii_code >= 48 and ascii_code <= 57

    @staticmethod
    def is_alpha(char: str) -> bool:
        """Check if the provided character is a letter (or underscore).

        These are the values that an ``identifier`` can begin with.

        Args:
            char: The character to evaluate.

        Returns:
            ``True`` if the provided char is a letter or underscore otherwise ``False``.
        """
        try:
            ascii_code = ord(char)
        except TypeError:
            # String passed instead of single char
            return False

        # lowercase a-z or uppercase A-Z or _
        return (
            (ascii_code >= 97 and ascii_code <= 122)
            or (ascii_code >= 65 and ascii_code <= 90)
            or ascii_code == 95
        )

    @staticmethod
    def is_alphanumeric(char: str) -> bool:
        """Check if the provided character is a letter, (underscore,) or number.

        These are the values that can be part of an ``identifier``.

        Args:
            char: The character to evaluate.

        Returns:
            ``True`` if the provided char is alphanumeric otherwise ``False``.
        """
        return Scanner.is_alpha(char) or Scanner.is_digit(char)

    def substr(self, start: int, length: int):
        """Extract a substring without advancing the cursor from it's current position.

        For example, to extract Hello you would call ``substr(4, 5)``::

            oOo Hello oOO
               ^-- Starting at the 4th character, read the next 5 characters.

        This is a little different that slicing strings which includes the first value
        and skips the last. (Also, it is a 0-index instead of 1). ``str[4,9]``.

        Args:
            start: The cursor position to start at.
            length: The length of the string to extract.

        Return:
            The string of ``length`` found at ``start``.
        """
        current_pos = self.current

        self.source.seek(start)
        value = self.source.read(length)

        self.source.seek(current_pos)

        return value
