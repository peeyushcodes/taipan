"""Taipan test suite — C Transpiler Integration Tests"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

from taipan.compiler.lexer.lexer import Lexer
from taipan.compiler.parser.parser import Parser
from taipan.compiler.c_transpiler.transpiler import CTranspiler

# Skip all C transpiler tests if no C compiler is available
CC = os.environ.get("CC", "gcc")
try:
    subprocess.run([CC, "--version"], capture_output=True, check=True)
    HAS_CC = True
except (FileNotFoundError, subprocess.CalledProcessError):
    HAS_CC = False

pytestmark = pytest.mark.skipif(not HAS_CC, reason=f"C compiler '{CC}' not available")

def run_c_compiled(source: str) -> str:
    """Lex, parse, transpile, compile with gcc, run, and return stdout."""
    # 1. Lex and Parse
    tokens = Lexer(source, "<test>").tokenize()
    ast = Parser(tokens, "<test>").parse()

    # 2. Transpile to C
    transpiler = CTranspiler()
    c_code = transpiler.transpile(ast)

    # 3. Write C code to a temp file and compile
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        c_file = tmpdir_path / "test_prog.c"
        c_file.write_text(c_code, encoding="utf-8")

        exe_file = tmpdir_path / "test_prog.exe" if sys.platform == "win32" else tmpdir_path / "test_prog"
        
        # Resolve the directory that contains taipan_runtime.h using the
        # installed package location so this works in both editable ("src/")
        # and installed layouts.
        import importlib.resources as _ir
        import taipan.compiler.c_transpiler as _ct_pkg
        try:
            # Python 3.9+ path
            c_transpiler_dir = Path(str(_ir.files(_ct_pkg)))
        except Exception:
            c_transpiler_dir = Path(_ct_pkg.__file__).parent

        cmd = [
            "gcc",
            "-O3",
            "-I", str(c_transpiler_dir),
            str(c_file),
            "-o", str(exe_file),
            "-lm"
        ]

        # Compile
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            pytest.fail(f"C Compilation Failed!\nCommand: {' '.join(cmd)}\nStderr: {res.stderr}\nC Code:\n{c_code}")

        # Run binary
        res_run = subprocess.run([str(exe_file)], capture_output=True, text=True)
        if res_run.returncode != 0:
            pytest.fail(f"Compiled binary exited with error code {res_run.returncode}\nStderr: {res_run.stderr}")

        return res_run.stdout.strip()


class TestCVariables:
    def test_let_integer(self):
        r = run_c_compiled('let x = 42\nshow(x)')
        assert r == "42"

    def test_let_string(self):
        r = run_c_compiled('let s = "hello"\nshow(s)')
        assert r == "hello"

    def test_let_bool(self):
        r = run_c_compiled('let b = true\nshow(b)')
        assert r == "true"

    def test_let_null(self):
        r = run_c_compiled('let n = null\nshow(n)')
        assert r == "null"

    def test_const(self):
        r = run_c_compiled('const X = 100\nshow(X)')
        assert r == "100"

    def test_augmented_assign(self):
        r = run_c_compiled('let x = 10\nx += 5\nshow(x)')
        assert r == "15"

    def test_variable_redefinition(self):
        r = run_c_compiled('let x = 10\nlet x = 20\nshow(x)')
        assert r == "20"


class TestCArithmetic:
    def test_add(self):      assert run_c_compiled('show(2 + 3)')     == "5"
    def test_sub(self):      assert run_c_compiled('show(10 - 4)')    == "6"
    def test_mul(self):      assert run_c_compiled('show(3 * 7)')     == "21"
    def test_div(self):      assert run_c_compiled('show(10 / 4)')    == "2.5"
    def test_mod(self):      assert run_c_compiled('show(10 % 3)')    == "1"
    def test_power(self):    assert run_c_compiled('show(2 ** 10)')   == "1024"
    def test_neg(self):      assert run_c_compiled('show(-5)')        == "-5"
    def test_string_concat(self): assert run_c_compiled('show("a" + "b")') == "ab"
    def test_precedence(self):    assert run_c_compiled('show(2 + 3 * 4)')  == "14"


class TestCComparisons:
    def test_eq(self): assert run_c_compiled('show(5 == 5)') == "true"
    def test_ne(self): assert run_c_compiled('show(5 != 3)') == "true"
    def test_lt(self): assert run_c_compiled('show(3 < 5)')  == "true"
    def test_le(self): assert run_c_compiled('show(5 <= 5)') == "true"
    def test_gt(self): assert run_c_compiled('show(5 > 3)')  == "true"
    def test_ge(self): assert run_c_compiled('show(5 >= 5)') == "true"


class TestCLogicalOps:
    def test_and_short_circuit_false(self):
        r = run_c_compiled('let x = false\nlet y = true\nshow(x and y)')
        assert r == "false"

    def test_and_short_circuit_true(self):
        r = run_c_compiled('let x = true\nlet y = 42\nshow(x and y)')
        assert r == "42"

    def test_or_short_circuit_true(self):
        r = run_c_compiled('let x = true\nlet y = false\nshow(x or y)')
        assert r == "true"

    def test_or_short_circuit_false(self):
        r = run_c_compiled('let x = false\nlet y = 100\nshow(x or y)')
        assert r == "100"


class TestCControlFlow:
    def test_if_then(self):
        r = run_c_compiled('let x = 10\nif x > 5 {\nshow("greater")\n}')
        assert r == "greater"

    def test_if_else(self):
        r = run_c_compiled('let x = 3\nif x > 5 {\nshow("greater")\n} else {\nshow("smaller")\n}')
        assert r == "smaller"

    def test_while_loop(self):
        r = run_c_compiled('let i = 0\nwhile i < 3 {\nshow(i)\ni += 1\n}')
        assert r == "0\n1\n2"

    def test_repeat_loop(self):
        r = run_c_compiled('repeat 3 {\nshow("rep")\n}')
        assert r == "rep\nrep\nrep"

    def test_for_range(self):
        r = run_c_compiled('for i in 1..4 {\nshow(i)\n}')
        assert r == "1\n2\n3"


class TestCFunctions:
    def test_simple_func(self):
        r = run_c_compiled('func hello() {\nshow("hi")\n}\nhello()')
        assert r == "hi"

    def test_func_args(self):
        r = run_c_compiled('func add(a, b) {\nreturn a + b\n}\nshow(add(2, 3))')
        assert r == "5"

    def test_recursive_fib(self):
        code = """
        func fib(n) {
            if n <= 1 {
                return n
            }
            return fib(n - 1) + fib(n - 2)
        }
        show(fib(10))
        """
        assert run_c_compiled(code) == "55"


class TestCLambdas:
    def test_simple_lambda(self):
        r = run_c_compiled('let f = (x) => x * 2\nshow(f(5))')
        assert r == "10"


class TestCMatch:
    def test_match_stmt(self):
        code = """
        let x = 2
        match x {
            case 1: { show("one") }
            case 2: { show("two") }
            default: { show("default") }
        }
        """
        assert run_c_compiled(code) == "two"
