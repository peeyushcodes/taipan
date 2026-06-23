"""
Taipan Token Definitions
=========================
Defines all token types used by the Taipan lexer and parser.
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import Any


class TokenType(Enum):
    # ── Literals ────────────────────────────────────────────────────────────
    INT         = auto()
    FLOAT       = auto()
    STRING      = auto()
    FSTRING     = auto()   # f"...{expr}..."  (interpolated string)
    BOOL        = auto()
    NULL        = auto()

    # ── Identifiers ─────────────────────────────────────────────────────────
    IDENTIFIER  = auto()

    # ── Keywords ─────────────────────────────────────────────────────────────
    LET         = auto()
    CONST       = auto()
    FUNC        = auto()
    CLASS       = auto()
    IF          = auto()
    ELSE        = auto()
    WHILE       = auto()
    FOR         = auto()
    REPEAT      = auto()
    RETURN      = auto()
    IMPORT      = auto()
    SPAWN       = auto()
    WAIT        = auto()
    TRY         = auto()
    CATCH       = auto()
    IN          = auto()
    AND         = auto()
    OR          = auto()
    NOT         = auto()
    TRUE        = auto()
    FALSE       = auto()
    AI          = auto()
    BREAK       = auto()
    CONTINUE    = auto()
    EXTENDS     = auto()
    SELF        = auto()
    SUPER       = auto()
    NEW         = auto()
    NULL_KW     = auto()
    MATCH       = auto()   # match statement
    CASE        = auto()   # case clause
    DEFAULT     = auto()   # default clause
    TEST        = auto()   # test statement (tai test)

    # ── Arithmetic Operators ─────────────────────────────────────────────────
    PLUS        = auto()   # +
    MINUS       = auto()   # -
    STAR        = auto()   # *
    SLASH       = auto()   # /
    PERCENT     = auto()   # %
    STAR_STAR   = auto()   # **  (power)
    SLASH_SLASH = auto()   # //  (floor div)

    # ── Assignment Operators ─────────────────────────────────────────────────
    EQUALS      = auto()   # =
    PLUS_EQ     = auto()   # +=
    MINUS_EQ    = auto()   # -=
    STAR_EQ     = auto()   # *=
    SLASH_EQ    = auto()   # /=

    # ── Comparison Operators ─────────────────────────────────────────────────
    EQ_EQ       = auto()   # ==
    NOT_EQ      = auto()   # !=
    LT          = auto()   # <
    LT_EQ       = auto()   # <=
    GT          = auto()   # >
    GT_EQ       = auto()   # >=

    # ── Logical Operators (symbolic) ─────────────────────────────────────────
    BANG        = auto()   # !

    # ── Punctuation ──────────────────────────────────────────────────────────
    LPAREN      = auto()   # (
    RPAREN      = auto()   # )
    LBRACE      = auto()   # {
    RBRACE      = auto()   # }
    LBRACKET    = auto()   # [
    RBRACKET    = auto()   # ]
    COMMA       = auto()   # ,
    DOT         = auto()   # .
    COLON       = auto()   # :
    SEMICOLON   = auto()   # ;
    ARROW       = auto()   # ->
    FAT_ARROW   = auto()   # => (lambda)
    DOT_DOT     = auto()   # .. (range)
    HASH        = auto()   # # (unused but reserved)
    PIPE        = auto()   # |
    AMPERSAND   = auto()   # &

    # ── Special ──────────────────────────────────────────────────────────────
    NEWLINE     = auto()
    EOF         = auto()
    COMMENT     = auto()


# ── Keyword map ──────────────────────────────────────────────────────────────
KEYWORDS: dict[str, TokenType] = {
    "let":      TokenType.LET,
    "const":    TokenType.CONST,
    "func":     TokenType.FUNC,
    "class":    TokenType.CLASS,
    "if":       TokenType.IF,
    "else":     TokenType.ELSE,
    "while":    TokenType.WHILE,
    "for":      TokenType.FOR,
    "repeat":   TokenType.REPEAT,
    "return":   TokenType.RETURN,
    "import":   TokenType.IMPORT,
    "spawn":    TokenType.SPAWN,
    "wait":     TokenType.WAIT,
    "try":      TokenType.TRY,
    "catch":    TokenType.CATCH,
    "in":       TokenType.IN,
    "and":      TokenType.AND,
    "or":       TokenType.OR,
    "not":      TokenType.NOT,
    "true":     TokenType.TRUE,
    "false":    TokenType.FALSE,
    "ai":       TokenType.AI,
    "break":    TokenType.BREAK,
    "continue": TokenType.CONTINUE,
    "extends":  TokenType.EXTENDS,
    "self":     TokenType.SELF,
    "super":    TokenType.SUPER,
    "new":      TokenType.NEW,
    "null":     TokenType.NULL_KW,
    "match":    TokenType.MATCH,
    "case":     TokenType.CASE,
    "default":  TokenType.DEFAULT,
    "test":     TokenType.TEST,
}


@dataclass
class Token:
    """A single lexical token produced by the Taipan lexer."""
    type:    TokenType
    value:   Any
    line:    int
    column:  int

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, {self.line}:{self.column})"
