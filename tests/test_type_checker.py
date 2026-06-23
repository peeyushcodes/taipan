"""Taipan test suite — Static Type Checker"""
from pathlib import Path
import pytest

from taipan.compiler.lexer.lexer import Lexer
from taipan.compiler.parser.parser import Parser
from taipan.compiler.semantic.type_checker import TypeChecker
from taipan.compiler.semantic.analyzer import SemanticAnalyzer

def get_type_errors(source: str) -> list[str]:
    """Parse and type-check source code. Returns list of error message strings."""
    tokens = Lexer(source, "<test>").tokenize()
    ast = Parser(tokens, "<test>").parse()
    
    # We must run SemanticAnalyzer first to match pipeline (optional but good hygiene)
    sem_analyzer = SemanticAnalyzer()
    sem_errors = sem_analyzer.analyze(ast)
    if sem_errors:
        return [e.message for e in sem_errors]
        
    checker = TypeChecker()
    errors = checker.check(ast)
    return [e.message for e in errors]


class TestTypeChecker:
    def test_correct_variable_decl(self):
        errors = get_type_errors('let x: Int = 42\nlet s: String = "hello"')
        assert len(errors) == 0

    def test_incorrect_variable_decl(self):
        errors = get_type_errors('let x: Int = "hello"')
        assert len(errors) == 1
        assert "Type mismatch" in errors[0]
        assert "cannot assign value of type 'String' to variable 'x' of type 'Int'" in errors[0]

    def test_widening_int_to_float(self):
        # Int can widen to Float automatically
        errors = get_type_errors('let x: Float = 42')
        assert len(errors) == 0

    def test_invalid_narrowing_float_to_int(self):
        errors = get_type_errors('let x: Int = 42.5')
        assert len(errors) == 1
        assert "Type mismatch" in errors[0]

    def test_assignment_type_safety(self):
        errors = get_type_errors('let x: Int = 10\nx = "hello"')
        assert len(errors) == 1
        assert "Type mismatch" in errors[0]
        assert "cannot assign type 'String' to variable 'x' of type 'Int'" in errors[0]

    def test_correct_function_call(self):
        code = """
        func add(a: Int, b: Int) -> Int {
            return a + b
        }
        add(2, 3)
        """
        errors = get_type_errors(code)
        assert len(errors) == 0

    def test_incorrect_function_call_args(self):
        code = """
        func add(a: Int, b: Int) -> Int {
            return a + b
        }
        add(2, "three")
        """
        errors = get_type_errors(code)
        assert len(errors) == 1
        assert "Argument type mismatch" in errors[0]
        assert "expected 'Int', got 'String'" in errors[0]

    def test_incorrect_function_call_count(self):
        code = """
        func add(a: Int, b: Int) -> Int {
            return a + b
        }
        add(2)
        """
        errors = get_type_errors(code)
        assert len(errors) == 1
        assert "Argument count mismatch" in errors[0]

    def test_incorrect_return_type(self):
        code = """
        func get_name() -> String {
            return 42
        }
        """
        errors = get_type_errors(code)
        assert len(errors) == 1
        assert "Incompatible return type" in errors[0]
        assert "declared 'String', got 'Int'" in errors[0]

    def test_invalid_subscript(self):
        errors = get_type_errors('let x = 10\nx[0]')
        assert len(errors) == 1
        assert "is not subscriptable" in errors[0]

    def test_invalid_index_type(self):
        errors = get_type_errors('let lst = []\nlst["first"]')
        assert len(errors) == 1
        assert "Index must be Int" in errors[0]

    def test_operator_mismatch(self):
        errors = get_type_errors('let x = 10 - "str"')
        assert len(errors) == 1
        assert "Operator '-' cannot be applied to types 'Int' and 'String'" in errors[0]

    def test_string_multiplication(self):
        # String * Int is valid in Taipan (desugars or evaluates as String)
        errors = get_type_errors('let x = "str" * 3')
        assert len(errors) == 0

    def test_lambda_type_check(self):
        # Lambdas are checked inside type checker
        errors = get_type_errors('let f = () => 5\nlet y: String = f()')
        assert len(errors) == 1
        assert "Type mismatch" in errors[0]

