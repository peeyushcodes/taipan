"""
Taipan Lexer
=============
Converts Taipan source text into a flat list of Tokens.

Usage:
    from taipan.compiler.lexer.lexer import Lexer
    tokens = Lexer(source_code, filename).tokenize()
"""

from typing import List
from taipan.compiler.lexer.tokens import Token, TokenType, KEYWORDS
from taipan.runtime.errors import TaipanLexError


class Lexer:
    """
    Character-by-character lexer for Taipan source code.
    Produces a list of Token objects (excluding COMMENT tokens).
    """

    def __init__(self, source: str, filename: str = "<stdin>"):
        self.source   = source
        self.filename = filename
        self.pos      = 0
        self.line     = 1
        self.column   = 1
        self.tokens: List[Token] = []

    # ── Public API ────────────────────────────────────────────────────────────

    def tokenize(self) -> List[Token]:
        """Lex the entire source and return the token list."""
        while not self._at_end():
            self._skip_whitespace_and_newlines()
            if self._at_end():
                break
            tok = self._next_token()
            if tok is not None and tok.type != TokenType.COMMENT:
                self.tokens.append(tok)

        self.tokens.append(Token(TokenType.EOF, None, self.line, self.column))
        return self.tokens

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _at_end(self) -> bool:
        return self.pos >= len(self.source)

    def _peek(self, offset: int = 0) -> str:
        idx = self.pos + offset
        if idx >= len(self.source):
            return "\0"
        return self.source[idx]

    def _advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def _match(self, expected: str) -> bool:
        if self._at_end() or self._peek() != expected:
            return False
        self._advance()
        return True

    def _make_token(self, ttype: TokenType, value=None,
                    line: int = None, col: int = None) -> Token:
        return Token(ttype, value, line or self.line, col or self.column)

    # ── Whitespace / comments ─────────────────────────────────────────────────

    def _skip_whitespace_and_newlines(self):
        while not self._at_end():
            ch = self._peek()
            if ch in (" ", "\t", "\r", "\n"):
                self._advance()
            elif ch == "/" and self._peek(1) == "/":
                self._skip_line_comment()
            elif ch == "/" and self._peek(1) == "*":
                self._skip_block_comment()
            else:
                break

    def _skip_line_comment(self):
        while not self._at_end() and self._peek() != "\n":
            self._advance()

    def _skip_block_comment(self):
        start_line = self.line
        self._advance()  # /
        self._advance()  # *
        while not self._at_end():
            if self._peek() == "*" and self._peek(1) == "/":
                self._advance()
                self._advance()
                return
            self._advance()
        raise TaipanLexError("Unterminated block comment", start_line, 1)

    # ── Main dispatch ─────────────────────────────────────────────────────────

    def _next_token(self) -> Token:
        line = self.line
        col  = self.column
        ch   = self._advance()

        # ── Numbers ──────────────────────────────────────────────────────────
        if ch.isdigit():
            return self._read_number(ch, line, col)

        # ── Strings ──────────────────────────────────────────────────────────
        if ch in ('"', "'"):
            return self._read_string(ch, line, col)

        # ── Identifiers / Keywords ────────────────────────────────────────────
        if ch.isalpha() or ch == "_":
            return self._read_identifier(ch, line, col)

        # ── Operators & punctuation ───────────────────────────────────────────
        return self._read_operator(ch, line, col)

    # ── Readers ───────────────────────────────────────────────────────────────

    def _read_number(self, first: str, line: int, col: int) -> Token:
        buf = first
        is_float = False

        while not self._at_end() and (self._peek().isdigit() or self._peek() == "_"):
            ch = self._advance()
            if ch != "_":
                buf += ch

        # Decimal point (but not ".." range operator)
        if self._peek() == "." and self._peek(1) != ".":
            is_float = True
            buf += self._advance()  # consume "."
            while not self._at_end() and self._peek().isdigit():
                buf += self._advance()

        # Scientific notation
        if self._peek() in ("e", "E"):
            is_float = True
            buf += self._advance()
            if self._peek() in ("+", "-"):
                buf += self._advance()
            if not self._peek().isdigit():
                raise TaipanLexError("Invalid scientific notation", line, col)
            while not self._at_end() and self._peek().isdigit():
                buf += self._advance()

        if is_float:
            return Token(TokenType.FLOAT, float(buf), line, col)
        return Token(TokenType.INT, int(buf), line, col)

    def _read_string(self, quote: str, line: int, col: int) -> Token:
        buf = ""
        while not self._at_end():
            ch = self._advance()
            if ch == quote:
                return Token(TokenType.STRING, buf, line, col)
            if ch == "\n":
                raise TaipanLexError("Unterminated string literal", line, col)
            if ch == "\\":
                escape = self._advance()
                mapping = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\",
                           "'": "'",  '"': '"',  "0": "\0"}
                if escape in mapping:
                    buf += mapping[escape]
                else:
                    buf += "\\" + escape
            else:
                buf += ch
        raise TaipanLexError("Unterminated string literal", line, col)

    def _read_identifier(self, first: str, line: int, col: int) -> Token:
        buf = first
        while not self._at_end() and (self._peek().isalnum() or self._peek() == "_"):
            buf += self._advance()

        ttype = KEYWORDS.get(buf, TokenType.IDENTIFIER)

        # F-string prefix: f"..." or f'...'
        if ttype == TokenType.IDENTIFIER and buf == "f" and self._peek() in ('"', "'"):
            quote = self._advance()
            return self._read_fstring(quote, line, col)

        # Boolean literals
        if ttype == TokenType.TRUE:
            return Token(TokenType.BOOL, True, line, col)
        if ttype == TokenType.FALSE:
            return Token(TokenType.BOOL, False, line, col)
        if ttype == TokenType.NULL_KW:
            return Token(TokenType.NULL, None, line, col)

        return Token(ttype, buf, line, col)

    def _read_fstring(self, quote: str, line: int, col: int) -> Token:
        """Read an f-string, producing a FSTRING token whose value is a
        list of ('lit', text) and ('expr', code_text) parts."""
        parts = []
        buf   = ""

        while not self._at_end():
            ch = self._advance()

            if ch == quote:
                # End of f-string
                if buf:
                    parts.append(("lit", buf))
                return Token(TokenType.FSTRING, parts, line, col)

            if ch == "\n":
                raise TaipanLexError("Unterminated f-string", line, col)

            if ch == "\\":
                esc = self._advance()
                mapping = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\",
                           "'": "'",  '"': '"',  "0": "\0"}
                buf += mapping.get(esc, "\\" + esc)
                continue

            if ch == "{":
                if self._peek() == "{":          # escaped {{ → literal {
                    self._advance()
                    buf += "{"
                    continue
                # Start of interpolation expression
                if buf:
                    parts.append(("lit", buf))
                    buf = ""
                expr_buf   = ""
                brace_depth = 1
                while not self._at_end() and brace_depth > 0:
                    ec = self._advance()
                    if ec == "{":
                        brace_depth += 1
                        expr_buf += ec
                    elif ec == "}":
                        brace_depth -= 1
                        if brace_depth > 0:
                            expr_buf += ec
                    else:
                        expr_buf += ec
                parts.append(("expr", expr_buf.strip()))
                continue

            if ch == "}":
                if self._peek() == "}":          # escaped }} → literal }
                    self._advance()
                    buf += "}"
                    continue
                raise TaipanLexError("Unmatched '}' in f-string", self.line, self.column)

            buf += ch

        raise TaipanLexError("Unterminated f-string", line, col)

    def _read_operator(self, ch: str, line: int, col: int) -> Token:
        def tok(ttype, val=None):
            return Token(ttype, val or ch, line, col)

        match ch:
            case "+":
                return tok(TokenType.PLUS_EQ, "+=") if self._match("=") else tok(TokenType.PLUS, "+")
            case "-":
                if self._match(">"):
                    return tok(TokenType.ARROW, "->")
                return tok(TokenType.MINUS_EQ, "-=") if self._match("=") else tok(TokenType.MINUS, "-")
            case "*":
                if self._match("*"):
                    return tok(TokenType.STAR_STAR, "**")
                return tok(TokenType.STAR_EQ, "*=") if self._match("=") else tok(TokenType.STAR, "*")
            case "/":
                if self._match("/"):
                    return tok(TokenType.SLASH_SLASH, "//")
                return tok(TokenType.SLASH_EQ, "/=") if self._match("=") else tok(TokenType.SLASH, "/")
            case "%":
                return tok(TokenType.PERCENT, "%")
            case "=":
                if self._match("="):
                    return tok(TokenType.EQ_EQ, "==")
                if self._match(">"):
                    return tok(TokenType.FAT_ARROW, "=>")
                return tok(TokenType.EQUALS, "=")
            case "!":
                return tok(TokenType.NOT_EQ, "!=") if self._match("=") else tok(TokenType.BANG, "!")
            case "<":
                return tok(TokenType.LT_EQ, "<=") if self._match("=") else tok(TokenType.LT, "<")
            case ">":
                return tok(TokenType.GT_EQ, ">=") if self._match("=") else tok(TokenType.GT, ">")
            case ".":
                if self._match("."):
                    return tok(TokenType.DOT_DOT, "..")
                return tok(TokenType.DOT, ".")
            case "(":  return tok(TokenType.LPAREN, "(")
            case ")":  return tok(TokenType.RPAREN, ")")
            case "{":  return tok(TokenType.LBRACE, "{")
            case "}":  return tok(TokenType.RBRACE, "}")
            case "[":  return tok(TokenType.LBRACKET, "[")
            case "]":  return tok(TokenType.RBRACKET, "]")
            case ",":  return tok(TokenType.COMMA, ",")
            case ":":  return tok(TokenType.COLON, ":")
            case ";":  return tok(TokenType.SEMICOLON, ";")
            case "|":  return tok(TokenType.PIPE, "|")
            case "&":  return tok(TokenType.AMPERSAND, "&")
            case "#":
                # treat as line comment
                while not self._at_end() and self._peek() != "\n":
                    self._advance()
                return Token(TokenType.COMMENT, None, line, col)
            case _:
                raise TaipanLexError(
                    f"Unexpected character '{ch}' (ord {ord(ch)})", line, col
                )
