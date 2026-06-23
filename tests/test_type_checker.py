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

    def test_parameter_type_inference_from_default(self):
        code = """
        func greet(name, greeting = "Hello") {
            return greeting
        }
        greet("Peeyush", 42) // should trigger error because greeting expects String
        """
        errors = get_type_errors(code)
        assert len(errors) == 1
        assert "Argument type mismatch" in errors[0]
        assert "expected 'String', got 'Int'" in errors[0]

    def test_function_return_type_inference(self):
        code = """
        func add(a: Int, b: Int) {
            return a + b
        }
        let res: String = add(2, 3) // should trigger mismatch since add returns Int
        """
        errors = get_type_errors(code)
        assert len(errors) == 1
        assert "Type mismatch" in errors[0]
        assert "cannot assign value of type 'Int' to variable 'res' of type 'String'" in errors[0]

    def test_recursive_function_return_type_inference(self):
        code = """
        func fib(n: Int) {
            if n <= 1 { return n }
            return fib(n - 1) + fib(n - 2)
        }
        let res: String = fib(10) // should trigger mismatch since fib returns Int
        """
        errors = get_type_errors(code)
        assert len(errors) == 1
        assert "Type mismatch" in errors[0]
        assert "cannot assign value of type 'Int'" in errors[0]

    def test_multiple_returns_unification(self):
        code = """
        func choose(cond: Bool, x: Int, y: Float) {
            if cond { return x }
            return y
        }
        let val: Float = choose(true, 10, 20.5) // should be Float due to Int/Float unification
        let err: Int = choose(true, 10, 20.5)   // should fail since unified is Float
        """
        errors = get_type_errors(code)
        assert len(errors) == 1
        assert "Type mismatch" in errors[0]
        assert "cannot assign value of type 'Float' to variable 'err' of type 'Int'" in errors[0]

    def test_generic_function_check(self):
        code = """
        func identity<T>(x: T) -> T {
            return x
        }
        let a: Int = identity(42)
        let b: String = identity("hello")
        let c: String = identity(42)
        """
        errors = get_type_errors(code)
        assert len(errors) == 1
        assert "Type mismatch" in errors[0]
        assert "cannot assign value of type 'Int' to variable 'c' of type 'String'" in errors[0]

    def test_generic_list_append(self):
        code = """
        let lst: List<Int> = []
        lst.append(42)
        lst.append("hello")
        """
        errors = get_type_errors(code)
        assert len(errors) == 1
        assert "Argument type mismatch: expected 'Int', got 'String'" in errors[0]

    def test_async_await_types(self):
        code = """
        async func compute(n: Int) -> Int {
            return n * 2
        }
        let p: Promise<Int> = compute(10)
        let res: Int = await p
        let err: String = await p
        """
        errors = get_type_errors(code)
        assert len(errors) == 1
        assert "Type mismatch" in errors[0]
        assert "cannot assign value of type 'Int' to variable 'err' of type 'String'" in errors[0]

    def test_await_non_promise(self):
        code = """
        let res: Int = await 42
        let err: String = await 42
        """
        errors = get_type_errors(code)
        assert len(errors) == 1
        assert "Type mismatch" in errors[0]
        assert "cannot assign value of type 'Int' to variable 'err' of type 'String'" in errors[0]



