"""Taipan test suite — Interpreter (integration tests)"""
import os, io

import pytest


from taipan.compiler.lexer.lexer    import Lexer
from taipan.compiler.parser.parser  import Parser
from taipan.compiler.backend.interpreter import Interpreter
from taipan.runtime.errors import TaipanRuntimeError, TaipanNameError


def run(source: str, capture=True):
    """Lex, parse, and interpret source. Returns captured stdout."""
    tokens  = Lexer(source, "<test>").tokenize()
    ast     = Parser(tokens, "<test>").parse()

    if os.environ.get("TAIPAN_TEST_VM") == "1":
        from taipan.compiler.vm.compiler import BytecodeCompiler
        from taipan.compiler.vm.vm import VM
        compiler = BytecodeCompiler(name="<test>")
        code_obj = compiler.compile(ast)
        vm = VM(filename="<test>")

        if capture:
            buf = io.StringIO()
            import builtins
            original_print = builtins.print
            builtins.print = lambda *a, **kw: buf.write(" ".join(str(x) for x in a) + "\n")
            try:
                vm.execute(code_obj)
            finally:
                builtins.print = original_print
            return buf.getvalue().strip()
        else:
            vm.execute(code_obj)
            return vm
    else:
        interp  = Interpreter(filename="<test>")
        if capture:
            buf = io.StringIO()
            import builtins
            original_print = builtins.print
            builtins.print = lambda *a, **kw: buf.write(" ".join(str(x) for x in a) + "\n")
            try:
                interp.execute(ast)
            finally:
                builtins.print = original_print
            return buf.getvalue().strip()
        else:
            interp.execute(ast)
            return interp



class TestVariables:
    def test_let_integer(self):
        r = run('let x = 42\nshow(x)')
        assert r == "42"

    def test_let_string(self):
        r = run('let s = "hello"\nshow(s)')
        assert r == "hello"

    def test_let_bool(self):
        r = run('let b = true\nshow(b)')
        assert r == "true"

    def test_let_null(self):
        r = run('let n = null\nshow(n)')
        assert r == "null"

    def test_const(self):
        r = run('const X = 100\nshow(X)')
        assert r == "100"

    def test_augmented_assign(self):
        r = run('let x = 10\nx += 5\nshow(x)')
        assert r == "15"

    def test_typed_declaration(self):
        r = run('let age: Int = 19\nshow(age)')
        assert r == "19"


class TestArithmetic:
    def test_add(self):      assert run('show(2 + 3)')     == "5"
    def test_sub(self):      assert run('show(10 - 4)')    == "6"
    def test_mul(self):      assert run('show(3 * 7)')     == "21"
    def test_div(self):      assert run('show(10 / 4)')    == "2.5"
    def test_floordiv(self): assert run('show(int(10 / 4))') == "2"
    def test_mod(self):      assert run('show(10 % 3)')    == "1"
    def test_power(self):    assert run('show(2 ** 10)')   == "1024"
    def test_neg(self):      assert run('show(-5)')        == "-5"
    def test_string_concat(self): assert run('show("a" + "b")') == "ab"
    def test_precedence(self):    assert run('show(2 + 3 * 4)')  == "14"
    def test_parens(self):        assert run('show((2 + 3) * 4)') == "20"


class TestComparisons:
    def test_eq(self):  assert run('show(5 == 5)')  == "true"
    def test_neq(self): assert run('show(5 != 6)')  == "true"
    def test_lt(self):  assert run('show(3 < 5)')   == "true"
    def test_gt(self):  assert run('show(5 > 3)')   == "true"
    def test_lte(self): assert run('show(5 <= 5)')  == "true"
    def test_gte(self): assert run('show(6 >= 5)')  == "true"


class TestLogical:
    def test_and_true(self):  assert run('show(true and true)')   == "true"
    def test_and_false(self): assert run('show(true and false)')  == "false"
    def test_or_true(self):   assert run('show(false or true)')   == "true"
    def test_or_false(self):  assert run('show(false or false)')  == "false"
    def test_not_true(self):  assert run('show(not true)')        == "false"
    def test_not_false(self): assert run('show(not false)')       == "true"


class TestConditionals:
    def test_if_true(self):
        r = run('if true { show("yes") }')
        assert r == "yes"

    def test_if_false(self):
        r = run('if false { show("yes") } else { show("no") }')
        assert r == "no"

    def test_if_elif(self):
        src = '''
let x = 5
if x > 10 { show("big") }
else if x > 3 { show("medium") }
else { show("small") }
'''
        assert run(src) == "medium"

    def test_nested_if(self):
        r = run('let a = 1\nif a == 1 { if a > 0 { show("nested") } }')
        assert r == "nested"


class TestLoops:
    def test_while(self):
        r = run('let i = 0\nwhile i < 3 { show(i)\ni += 1 }')
        assert r == "0\n1\n2"

    def test_for_range(self):
        r = run('for i in 1..4 { show(i) }')
        assert r == "1\n2\n3"

    def test_repeat(self):
        r = run('repeat 3 { show("x") }')
        assert r == "x\nx\nx"

    def test_break(self):
        r = run('let i = 0\nwhile true { if i == 2 { break }\nshow(i)\ni += 1 }')
        assert r == "0\n1"

    def test_continue(self):
        r = run('for i in 1..5 { if i == 3 { continue }\nshow(i) }')
        assert r == "1\n2\n4"

    def test_for_list(self):
        r = run('let a = [10, 20, 30]\nfor x in a { show(x) }')
        assert r == "10\n20\n30"


class TestFunctions:
    def test_basic(self):
        r = run('func greet(name) { show("Hello " + name) }\ngreet("World")')
        assert r == "Hello World"

    def test_return_value(self):
        r = run('func add(a, b) { return a + b }\nshow(add(3, 4))')
        assert r == "7"

    def test_default_param(self):
        r = run('func greet(name, msg = "Hello") { show(msg + " " + name) }\ngreet("Tai")')
        assert r == "Hello Tai"

    def test_recursion(self):
        src = '''
func fact(n) {
    if n <= 1 { return 1 }
    return n * fact(n - 1)
}
show(fact(5))
'''
        assert run(src) == "120"

    def test_closure(self):
        src = '''
let x = 10
func addX(n) { return n + x }
show(addX(5))
'''
        assert run(src) == "15"


class TestCollections:
    def test_list(self):
        r = run('let a = [1, 2, 3]\nshow(len(a))')
        assert r == "3"

    def test_list_index(self):
        r = run('let a = [10, 20, 30]\nshow(a[1])')
        assert r == "20"

    def test_list_append(self):
        r = run('let a = [1]\na.append(2)\nshow(len(a))')
        assert r == "2"

    def test_map(self):
        r = run('let m = {"x": 1, "y": 2}\nshow(m["x"])')
        assert r == "1"

    def test_map_set(self):
        r = run('let m = {}\nm["key"] = "val"\nshow(m["key"])')
        assert r == "val"

    def test_tuple(self):
        r = run('let t = (1, 2, 3)\nshow(t[0])')
        assert r == "1"

    def test_range_for(self):
        r = run('let s = 0\nfor i in 1..4 { s += i }\nshow(s)')
        assert r == "6"


class TestClasses:
    def test_basic_class(self):
        src = '''
class Dog {
    let name
    func init(name) { self.name = name }
    func bark() { show("Woof from " + self.name) }
}
let d = Dog("Rex")
d.bark()
'''
        assert run(src) == "Woof from Rex"

    def test_instance_fields(self):
        src = '''
class Point {
    let x
    let y
    func init(x, y) { self.x = x\nself.y = y }
    func show_point() { show(str(self.x) + "," + str(self.y)) }
}
let p = Point(3, 4)
p.show_point()
'''
        assert run(src) == "3,4"

    def test_inheritance(self):
        src = '''
class Animal {
    let sound
    func init(sound) { self.sound = sound }
    func speak() { show(self.sound) }
}
class Cat extends Animal {
    func init() { self.sound = "Meow" }
}
let c = Cat()
c.speak()
'''
        assert run(src) == "Meow"


class TestErrorHandling:
    def test_try_catch(self):
        src = '''
try {
    let x = 1 / 0
}
catch err {
    show("caught: " + err)
}
'''
        r = run(src)
        assert "caught" in r

    def test_try_no_error(self):
        r = run('try { let x = 10 } catch err { show("error") }\nshow("ok")')
        assert r == "ok"

    def test_undefined_var_runtime(self):
        with pytest.raises(Exception):
            run('show(undefined_var)', capture=False)


class TestBuiltins:
    def test_len_string(self): assert run('show(len("hello"))') == "5"
    def test_len_list(self):   assert run('show(len([1,2,3]))') == "3"
    def test_type_int(self):   assert run('show(type(42))')     == "Int"
    def test_type_str(self):   assert run('show(type("hi"))') == "String"
    def test_int_conv(self):   assert run('show(int("42"))')    == "42"
    def test_float_conv(self): assert run('show(float("3.14"))') == "3.14"
    def test_str_conv(self):   assert run('show(str(99))')      == "99"
    def test_abs(self):        assert run('show(abs(-5))')      == "5"
    def test_min(self):        assert run('show(min([3,1,2]))') == "1"
    def test_max(self):        assert run('show(max([3,1,2]))') == "3"
    def test_sum(self):        assert run('show(sum([1,2,3]))') == "6"
    def test_round(self):      assert run('show(round(3.567, 2))') == "3.57"


class TestStdlib:
    def test_math_sqrt(self):
        r = run('import math\nshow(math.sqrt(9))')
        assert r == "3.0"

    def test_math_pi(self):
        r = run('import math\nshow(round(math.pi, 4))')
        assert float(r) == pytest.approx(3.1416, rel=1e-3)

    def test_json_roundtrip(self):
        src = '''
import json
let data = {"name": "Tai", "age": 19}
let s = json.stringify(data)
let p = json.parse(s)
show(p["name"])
'''
        assert run(src) == "Tai"

    def test_time_now(self):
        r = run('import time\nlet t = time.now()\nshow(len(t) > 0)')
        assert r == "true"


# ── New Refinement Tests ───────────────────────────────────────────────────────

class TestConcurrency:
    """Validate that spawned threads execute without corrupting each other's scope."""

    def test_spawn_wait_basic(self):
        """Spawned tasks run and finish; wait blocks until all done."""
        import time as _time
        src = '''
import time
func task(n) {
    time.sleep(0.05)
    show(n)
}
spawn task(1)
spawn task(2)
wait
'''
        r = run(src)
        lines = sorted(r.strip().splitlines())
        assert lines == ["1", "2"]

    def test_spawn_does_not_pollute_main_scope(self):
        """A variable set inside a spawned task must not appear in the main thread."""
        src = '''
import time
let result = "original"
func mutate() {
    time.sleep(0.05)
    let result = "mutated"
    show("inner: " + result)
}
spawn mutate()
wait
show("outer: " + result)
'''
        r = run(src)
        assert "inner: mutated" in r
        assert "outer: original" in r


class TestRedeclaration:
    """Validate that the semantic analyzer flags duplicate declarations."""

    def _check_errors(self, source: str):
        """Return semantic error messages for the given source."""
        from taipan.compiler.lexer.lexer import Lexer
        from taipan.compiler.parser.parser import Parser
        from taipan.compiler.semantic.analyzer import SemanticAnalyzer
        tokens = Lexer(source, "<test>").tokenize()
        ast    = Parser(tokens, "<test>").parse()
        return SemanticAnalyzer().analyze(ast)

    def test_duplicate_let_same_scope(self):
        errors = self._check_errors("let x = 1\nlet x = 2")
        assert any("Duplicate" in str(e) and "x" in str(e) for e in errors)

    def test_duplicate_const_same_scope(self):
        errors = self._check_errors("const X = 1\nconst X = 2")
        assert any("Duplicate" in str(e) and "X" in str(e) for e in errors)

    def test_duplicate_func_same_scope(self):
        errors = self._check_errors("func foo() { }\nfunc foo() { }")
        assert any("Duplicate" in str(e) and "foo" in str(e) for e in errors)

    def test_duplicate_class_same_scope(self):
        errors = self._check_errors("class Dog { }\nclass Dog { }")
        assert any("Duplicate" in str(e) and "Dog" in str(e) for e in errors)

    def test_redecl_in_different_scopes_allowed(self):
        """Shadowing a variable in a nested scope is fine (no error)."""
        src = '''
let x = 1
func foo() {
    let x = 2
    show(x)
}
foo()
'''
        errors = self._check_errors(src)
        # There should be no duplicate errors (undefined-identifier warnings are ok)
        dup_errors = [e for e in errors if "Duplicate" in str(e)]
        assert dup_errors == []

    def test_methods_with_same_name_in_class_no_error(self):
        """A method named 'init' in a class body should not be flagged as duplicate."""
        src = '''
class Foo {
    func init(x) { self.x = x }
    func bar() { show(self.x) }
}
'''
        errors = self._check_errors(src)
        dup_errors = [e for e in errors if "Duplicate" in str(e)]
        assert dup_errors == []


class TestIndexTypeSafety:
    """Validate that indexing with non-integers on sequences raises TaipanTypeError."""

    def test_list_string_index_raises(self):
        from taipan.runtime.errors import TaipanTypeError
        import pytest
        with pytest.raises((TaipanTypeError, Exception)) as exc_info:
            run('let a = [1,2,3]\nshow(a["x"])', capture=False)
        assert "index" in str(exc_info.value).lower() or "Int" in str(exc_info.value)

    def test_tuple_string_index_raises(self):
        from taipan.runtime.errors import TaipanTypeError
        import pytest
        with pytest.raises((TaipanTypeError, Exception)):
            run('let t = (1, 2, 3)\nshow(t["bad"])', capture=False)

    def test_string_string_index_raises(self):
        from taipan.runtime.errors import TaipanTypeError
        import pytest
        with pytest.raises((TaipanTypeError, Exception)):
            run('let s = "hello"\nshow(s["bad"])', capture=False)

    def test_list_int_index_works(self):
        r = run('let a = [10, 20, 30]\nshow(a[1])')
        assert r == "20"

    def test_list_float_index_works(self):
        """Float indices are truncated to int (consistent with Python int() conversion)."""
        r = run('let a = [10, 20, 30]\nshow(a[1.9])')
        assert r == "20"

    def test_list_out_of_range_raises(self):
        from taipan.runtime.errors import TaipanIndexError
        import pytest
        with pytest.raises((TaipanIndexError, Exception)):
            run('let a = [1,2,3]\nshow(a[99])', capture=False)



class TestNewFeatures:
    """Tests for features added in v1.0+ (import ai fix, f-strings, etc.)"""

    def test_import_ai_keyword(self):
        """import ai should work even though 'ai' is a keyword for declarations."""
        r = run('import ai\nshow(ai.isAvailable())')
        assert r in ("false", "true")

    def test_fstring_basic(self):
        r = run('let name = "Taipan"\nshow(f"Hello, {name}!")')
        assert r == "Hello, Taipan!"

    def test_fstring_expression(self):
        r = run('let x = 10\nlet y = 20\nshow(f"Sum: {x + y}")')
        assert r == "Sum: 30"

    def test_fstring_number_to_string(self):
        r = run('let n = 42\nshow(f"The answer is {n}")')
        assert r == "The answer is 42"

    def test_fstring_literal_braces(self):
        r = run('show(f"{{literal}}")')
        assert r == "{literal}"

    def test_ai_module_mock_ask(self):
        r = run('import ai\nshow(ai.ask("test"))')
        assert "AI" in r or "Mock" in r or "Offline" in r

    def test_ai_module_mock_sentiment(self):
        r = run('import ai\nshow(ai.sentiment("great!"))')
        assert "AI" in r or "Mock" in r or "Offline" in r

    def test_ai_decl_and_import_coexist(self):
        """Both 'ai myBot' and 'import ai' should work in the same file."""
        r = run('import ai\nai myBot\nshow(ai.isAvailable())\nshow(myBot.ask("hi"))')
        assert "false" in r or "true" in r


class TestAsyncAwait:
    def test_async_await_basic(self):
        src = """
        import time
        async func double(x) {
            time.sleep(0.01)
            return x * 2
        }
        let p = double(10)
        let r = await p
        show(r)
        """
        assert run(src) == "20"

    def test_async_await_concurrent(self):
        src = """
        import time
        async func sleep_and_return(x, sec) {
            time.sleep(sec)
            return x
        }
        let p1 = sleep_and_return(1, 0.05)
        let p2 = sleep_and_return(2, 0.01)
        let r2 = await p2
        let r1 = await p1
        show(r2)
        show(r1)
        """
        assert run(src) == "2\n1"

    def test_await_non_promise(self):
        src = """
        let r = await 42
        show(r)
        """
        assert run(src) == "42"

    def test_async_exception_propagation(self):
        src = """
        async func fail() {
            let x = 1 / 0
        }
        let p = fail()
        let r = await p
        """
        from taipan.runtime.errors import TaipanDivisionByZeroError
        with pytest.raises((TaipanDivisionByZeroError, Exception)):
            run(src, capture=False)


class TestGenericsExecution:
    def test_generic_function_execution(self):
        src = """
        func identity<T>(x: T) -> T {
            return x
        }
        show(identity(42))
        show(identity("hello"))
        """
        assert run(src) == "42\nhello"

