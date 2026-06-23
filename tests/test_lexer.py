"""Taipan test suite — Lexer"""
import pytest
from taipan.compiler.lexer.lexer import Lexer
from taipan.compiler.lexer.tokens import TokenType


def lex(src):
    return Lexer(src, "<test>").tokenize()


def types(src):
    return [t.type for t in lex(src) if t.type != TokenType.EOF]


class TestLiterals:
    def test_integer(self):
        toks = lex("42")
        assert toks[0].type  == TokenType.INT
        assert toks[0].value == 42

    def test_float(self):
        toks = lex("3.14")
        assert toks[0].type  == TokenType.FLOAT
        assert abs(toks[0].value - 3.14) < 1e-10

    def test_string_double(self):
        toks = lex('"hello"')
        assert toks[0].type  == TokenType.STRING
        assert toks[0].value == "hello"

    def test_string_single(self):
        toks = lex("'world'")
        assert toks[0].type  == TokenType.STRING
        assert toks[0].value == "world"

    def test_string_escape(self):
        toks = lex(r'"hello\nworld"')
        assert toks[0].value == "hello\nworld"

    def test_bool_true(self):
        toks = lex("true")
        assert toks[0].type  == TokenType.BOOL
        assert toks[0].value == True

    def test_bool_false(self):
        toks = lex("false")
        assert toks[0].type  == TokenType.BOOL
        assert toks[0].value == False

    def test_null(self):
        toks = lex("null")
        assert toks[0].type == TokenType.NULL


class TestKeywords:
    def test_let(self):      assert types("let")[0]    == TokenType.LET
    def test_const(self):    assert types("const")[0]  == TokenType.CONST
    def test_func(self):     assert types("func")[0]   == TokenType.FUNC
    def test_class(self):    assert types("class")[0]  == TokenType.CLASS
    def test_if(self):       assert types("if")[0]     == TokenType.IF
    def test_else(self):     assert types("else")[0]   == TokenType.ELSE
    def test_while(self):    assert types("while")[0]  == TokenType.WHILE
    def test_for(self):      assert types("for")[0]    == TokenType.FOR
    def test_repeat(self):   assert types("repeat")[0] == TokenType.REPEAT
    def test_return(self):   assert types("return")[0] == TokenType.RETURN
    def test_import(self):   assert types("import")[0] == TokenType.IMPORT
    def test_spawn(self):    assert types("spawn")[0]  == TokenType.SPAWN
    def test_wait(self):     assert types("wait")[0]   == TokenType.WAIT
    def test_try(self):      assert types("try")[0]    == TokenType.TRY
    def test_catch(self):    assert types("catch")[0]  == TokenType.CATCH
    def test_in(self):       assert types("in")[0]     == TokenType.IN
    def test_and(self):      assert types("and")[0]    == TokenType.AND
    def test_or(self):       assert types("or")[0]     == TokenType.OR
    def test_not(self):      assert types("not")[0]    == TokenType.NOT
    def test_ai(self):       assert types("ai")[0]     == TokenType.AI


class TestOperators:
    def test_arithmetic(self):
        t = types("+ - * / % **")
        assert t == [TokenType.PLUS, TokenType.MINUS, TokenType.STAR,
                     TokenType.SLASH, TokenType.PERCENT, TokenType.STAR_STAR]

    def test_comparison(self):
        t = types("== != < <= > >=")
        assert t == [TokenType.EQ_EQ, TokenType.NOT_EQ, TokenType.LT,
                     TokenType.LT_EQ, TokenType.GT, TokenType.GT_EQ]

    def test_augmented(self):
        t = types("+= -= *= /=")
        assert t == [TokenType.PLUS_EQ, TokenType.MINUS_EQ,
                     TokenType.STAR_EQ, TokenType.SLASH_EQ]

    def test_arrow(self):
        assert types("->")[0] == TokenType.ARROW

    def test_range(self):
        assert types("..")[0] == TokenType.DOT_DOT


class TestPunctuation:
    def test_brackets(self):
        t = types("( ) { } [ ]")
        assert t == [TokenType.LPAREN, TokenType.RPAREN, TokenType.LBRACE,
                     TokenType.RBRACE, TokenType.LBRACKET, TokenType.RBRACKET]

    def test_comma_colon_dot(self):
        t = types(", : .")
        assert t == [TokenType.COMMA, TokenType.COLON, TokenType.DOT]


class TestComments:
    def test_line_comment_skipped(self):
        t = types("let x = 1 // this is a comment\nlet y = 2")
        assert TokenType.COMMENT not in t

    def test_block_comment_skipped(self):
        t = types("let /* this is ignored */ x = 1")
        assert TokenType.COMMENT not in t


class TestComplex:
    def test_let_declaration(self):
        t = types("let name = \"Peeyush\"")
        assert t == [TokenType.LET, TokenType.IDENTIFIER, TokenType.EQUALS, TokenType.STRING]

    def test_function_call(self):
        t = types("show(\"hello\")")
        assert t == [TokenType.IDENTIFIER, TokenType.LPAREN, TokenType.STRING, TokenType.RPAREN]

    def test_range_expression(self):
        t = types("1..10")
        assert t == [TokenType.INT, TokenType.DOT_DOT, TokenType.INT]

    def test_line_numbers(self):
        toks = lex("let\nx\n=\n1")
        lines = [t.line for t in toks if t.type != TokenType.EOF]
        assert lines == [1, 2, 3, 4]
