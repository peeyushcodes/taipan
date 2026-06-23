"""
Taipan Tree-Walk Interpreter
==============================
Walks the AST and executes each node directly.

Supports:
  - All primitive and collection types
  - Variables, constants, functions, classes, inheritance
  - Control flow: if/else, while, for, repeat, break, continue
  - Error handling: try/catch
  - Concurrency: spawn / wait (via Python threading)
  - Module imports (stdlib)
  - AI assistant declarations
  - Full built-in function library
"""

from __future__ import annotations
import threading
import sys
import os
from typing import Any, List, Optional

from taipan.compiler.ast.nodes import *
from taipan.runtime.environment import Environment
from taipan.runtime.errors import (
    TaipanRuntimeError, TaipanTypeError, TaipanNameError,
    TaipanIndexError, TaipanAttributeError, TaipanValueError,
    TaipanDivisionByZeroError, ReturnSignal, BreakSignal, ContinueSignal,
)
from taipan.runtime.taipan_types import (
    PeeList, PeeMap, PeeSet, PeeTuple, PeeRange,
    PeeFunction, PeeClass, PeeInstance, BoundMethod, PeeAI,
    pee_str, pee_truthy, PeePromise,
)


# ── Stdlib loader ──────────────────────────────────────────────────────────────

def _load_stdlib_module(name: str) -> Optional[PeeMap]:
    """Load a standard library module and return it as a PeeMap of callables."""
    try:
        mod_map = {
            "math":        "taipan.stdlib.math_module",
            "string":      "taipan.stdlib.string_module",
            "file":        "taipan.stdlib.file_module",
            "json":        "taipan.stdlib.json_module",
            "time":        "taipan.stdlib.time_module",
            "collections": "taipan.stdlib.collections_module",
            "network":     "taipan.stdlib.network_module",
            "ai":          "taipan.stdlib.ai_module",
        }.get(name)

        if mod_map is None:
            return None

        import importlib
        mod = importlib.import_module(mod_map)
        if hasattr(mod, "get_module"):
            return mod.get_module()
        return None
    except ImportError:
        return None


# ── Interpreter ───────────────────────────────────────────────────────────────

class Interpreter:
    """Tree-walk interpreter for Taipan AST."""

    def __init__(self, filename: str = "<stdin>"):
        self.filename    = filename
        self._threads:   List[threading.Thread] = []
        self._threads_lock = threading.Lock()
        self.globals     = Environment(name="global")
        self._setup_builtins(self.globals)
        # Thread-local storage for `env` so each spawned thread gets its own
        # environment pointer without interfering with sibling threads.
        self._tls        = threading.local()
        self._tls.env    = self.globals
        self._module_cache: dict = {}   # path → PeeMap for user .pk modules
        self._test_results: list = []    # test "name" { ... } results

    # ── Thread-local env property ─────────────────────────────────────────────

    @property
    def env(self) -> Environment:
        """Return this thread's current environment (defaults to globals)."""
        tls = self.__dict__.get("_tls")
        if tls is None:
            return self.__dict__.get("globals", None)
        return getattr(tls, "env", self.__dict__.get("globals", None))

    @env.setter
    def env(self, value: Environment):
        """Set this thread's current environment."""
        tls = self.__dict__.get("_tls")
        if tls is None:
            return
        tls.env = value

    # ── Public API ────────────────────────────────────────────────────────────

    def execute(self, node: Node) -> Any:
        """Execute a program or statement node."""
        return self._exec(node)

    def evaluate(self, node: Node) -> Any:
        """Evaluate an expression node and return its value."""
        return self._eval(node)

    # ── Built-ins setup ───────────────────────────────────────────────────────

    def _setup_builtins(self, env: Environment):
        builtins = {
            "show":     self._builtin_show,
            "print":    self._builtin_show,
            "input":    self._builtin_input,
            "len":      self._builtin_len,
            "type":     self._builtin_type,
            "int":      self._builtin_int,
            "float":    self._builtin_float,
            "str":      self._builtin_str,
            "bool":     self._builtin_bool,
            "range":    self._builtin_range,
            "list":     self._builtin_list,
            "set":      self._builtin_set,
            "map":      self._builtin_map_fn,
            "abs":      lambda args: abs(self._require_num(args, 0, "abs")),
            "min":      lambda args: min(self._iter_args(args)),
            "max":      lambda args: max(self._iter_args(args)),
            "sum":      lambda args: sum(self._iter_args(args)),
            "round":    lambda args: round(self._require_num(args, 0, "round"),
                                           int(args[1]) if len(args) > 1 else 0),
            "sorted":   self._builtin_sorted,
            "reversed": self._builtin_reversed,
            "exit":     lambda args: sys.exit(int(args[0]) if args else 0),
            "assert":   self._builtin_assert,
            "format":   self._builtin_format,
            "chr":      lambda args: chr(int(args[0])),
            "ord":      lambda args: ord(str(args[0])[0]),
            "hex":      lambda args: hex(int(args[0])),
            "bin":      lambda args: bin(int(args[0])),
        }
        for name, fn in builtins.items():
            env.define(name, PeeFunction(
                name=name, params=[], body=None, closure=env,
                is_builtin=True, builtin_fn=fn
            ))

    # ── Built-in implementations ──────────────────────────────────────────────

    def _builtin_show(self, args: list):
        parts = [pee_str(a) for a in args]
        print(" ".join(parts))
        return None

    def _builtin_input(self, args: list):
        prompt = pee_str(args[0]) if args else ""
        return input(prompt)

    def _builtin_len(self, args: list):
        v = args[0] if args else None
        if isinstance(v, (str, PeeList, PeeMap, PeeSet, PeeTuple)):
            return len(v)
        if isinstance(v, PeeRange):
            stop = v.end + (1 if v.inclusive else 0)
            return max(0, (stop - v.start + v.step - 1) // v.step)
        raise TaipanTypeError(f"len() does not support type {type(v).__name__}")

    def _builtin_type(self, args: list):
        v = args[0] if args else None
        type_map = {
            int: "Int", float: "Float", str: "String", bool: "Bool",
            type(None): "Null",
            PeeList: "List", PeeMap: "Map", PeeSet: "Set", PeeTuple: "Tuple",
            PeeRange: "Range", PeeFunction: "Function",
            PeeClass: "Class", PeeInstance: "Instance",
            BoundMethod: "BoundMethod", PeeAI: "AI",
            PeePromise: "Promise",
        }
        return type_map.get(type(v), type(v).__name__)

    def _builtin_int(self, args: list):
        v = args[0] if args else 0
        try:
            if isinstance(v, bool): return int(v)
            return int(v)
        except (ValueError, TypeError):
            raise TaipanTypeError(f"Cannot convert {v!r} to Int")

    def _builtin_float(self, args: list):
        v = args[0] if args else 0.0
        try: return float(v)
        except (ValueError, TypeError):
            raise TaipanTypeError(f"Cannot convert {v!r} to Float")

    def _builtin_str(self, args: list):
        return pee_str(args[0]) if args else ""

    def _builtin_bool(self, args: list):
        return pee_truthy(args[0]) if args else False

    def _builtin_range(self, args: list):
        if len(args) == 1:
            return PeeRange(0, int(args[0]), 1, inclusive=False)
        elif len(args) == 2:
            return PeeRange(int(args[0]), int(args[1]), 1, inclusive=False)
        else:
            return PeeRange(int(args[0]), int(args[1]), int(args[2]), inclusive=False)

    def _builtin_list(self, args: list):
        if not args: return PeeList()
        v = args[0]
        if isinstance(v, PeeList): return PeeList(v._data[:])
        if isinstance(v, (PeeSet, PeeTuple)): return PeeList(list(v._data))
        if isinstance(v, PeeRange): return PeeList(list(v))
        if isinstance(v, str): return PeeList(list(v))
        raise TaipanTypeError(f"Cannot convert {type(v).__name__} to List")

    def _builtin_set(self, args: list):
        if not args: return PeeSet()
        v = args[0]
        if isinstance(v, PeeList): return PeeSet(v._data)
        if isinstance(v, PeeSet): return PeeSet(v._data)
        raise TaipanTypeError(f"Cannot convert {type(v).__name__} to Set")

    def _builtin_map_fn(self, args: list):
        return PeeMap()

    def _builtin_sorted(self, args: list):
        v = args[0] if args else PeeList()
        if isinstance(v, PeeList):
            return PeeList(sorted(v._data, key=lambda x: (str(type(x)), x)
                                  if not isinstance(x, (int, float, str)) else x))
        raise TaipanTypeError("sorted() requires a List")

    def _builtin_reversed(self, args: list):
        v = args[0] if args else PeeList()
        if isinstance(v, PeeList):
            return PeeList(list(reversed(v._data)))
        raise TaipanTypeError("reversed() requires a List")

    def _builtin_assert(self, args: list):
        cond = pee_truthy(args[0]) if args else False
        msg  = pee_str(args[1]) if len(args) > 1 else "Assertion failed"
        if not cond:
            raise TaipanRuntimeError(msg)
        return None

    def _builtin_format(self, args: list):
        if not args: return ""
        template = str(args[0])
        vals = args[1:]
        for i, v in enumerate(vals):
            template = template.replace(f"{{{i}}}", pee_str(v))
        return template

    def _require_num(self, args, idx, fname):
        v = args[idx] if idx < len(args) else 0
        if not isinstance(v, (int, float)):
            raise TaipanTypeError(f"{fname}() requires a number, got {type(v).__name__}")
        return v

    def _iter_args(self, args):
        if len(args) == 1 and isinstance(args[0], PeeList):
            return iter(args[0])
        return iter(args)

    # ── Execution dispatch ────────────────────────────────────────────────────

    def _exec(self, node: Node) -> Any:
        method = f"_exec_{type(node).__name__}"
        fn = getattr(self, method, None)
        if fn:
            return fn(node)
        # Fallback: try as expression
        return self._eval(node)

    def _eval(self, node: Node) -> Any:
        method = f"_eval_{type(node).__name__}"
        fn = getattr(self, method, None)
        if fn:
            return fn(node)
        raise TaipanRuntimeError(
            f"Cannot evaluate node type '{type(node).__name__}'",
            node.line, node.column
        )

    # ── Statement executors ───────────────────────────────────────────────────

    def _exec_Program(self, node: Program):
        for stmt in node.body:
            self._exec(stmt)

    def _exec_Block(self, node: Block):
        for stmt in node.statements:
            self._exec(stmt)

    def _exec_ExpressionStmt(self, node: ExpressionStmt):
        return self._eval(node.expression)

    def _exec_VariableDecl(self, node: VariableDecl):
        value = self._eval(node.value) if node.value is not None else None
        self.env.define(node.name, value, constant=False)

    def _exec_ConstDecl(self, node: ConstDecl):
        value = self._eval(node.value)
        self.env.define(node.name, value, constant=True)

    def _exec_AssignStmt(self, node: AssignStmt):
        value = self._eval(node.value)

        if node.operator != "=":
            # Augmented assignment: first get current value
            current = self._eval(node.target)
            op = node.operator[:-1]  # "+" from "+="
            value = self._apply_binary(current, op, value, node.line, node.column)

        self._assign_target(node.target, value, node.line, node.column)

    def _assign_target(self, target: Node, value: Any, line: int, col: int):
        if isinstance(target, Identifier):
            try:
                self.env.set(target.name, value, line, col)
            except TaipanNameError:
                self.env.define(target.name, value)
        elif isinstance(target, MemberExpr):
            obj = self._eval(target.object)
            if isinstance(obj, PeeInstance):
                obj.set(target.property, value)
            elif isinstance(obj, PeeMap):
                obj[target.property] = value
            else:
                raise TaipanAttributeError(
                    f"Cannot set property on {type(obj).__name__}", line, col
                )
        elif isinstance(target, IndexExpr):
            obj = self._eval(target.object)
            idx = self._eval(target.index)
            if isinstance(obj, PeeList):
                try:
                    obj[int(idx)] = value
                except IndexError:
                    raise TaipanIndexError(f"List index {idx} out of range", line, col)
            elif isinstance(obj, PeeMap):
                obj[idx] = value
            else:
                raise TaipanTypeError(f"Cannot index-assign into {type(obj).__name__}", line, col)
        else:
            raise TaipanRuntimeError(f"Invalid assignment target", line, col)

    def _exec_FunctionDecl(self, node: FunctionDecl):
        fn = PeeFunction(
            name=node.name,
            params=node.params,
            body=node.body,
            closure=self.env,
            is_async=node.is_async,
        )
        self.env.define(node.name, fn)

    def _exec_ClassDecl(self, node: ClassDecl):
        superclass = None
        if node.superclass:
            sc = self.env.get(node.superclass, node.line, node.column)
            if not isinstance(sc, PeeClass):
                raise TaipanTypeError(
                    f"'{node.superclass}' is not a class", node.line, node.column
                )
            superclass = sc

        # Collect methods
        methods: dict[str, PeeFunction] = {}
        for stmt in node.body.statements:
            if isinstance(stmt, FunctionDecl):
                fn = PeeFunction(
                    name=stmt.name,
                    params=stmt.params,
                    body=stmt.body,
                    closure=self.env,
                    is_method=True,
                )
                methods[stmt.name] = fn
            elif isinstance(stmt, (VariableDecl, ConstDecl)):
                # Class-level attribute default: treated as instance field
                pass  # initialized in __init__ if present

        klass = PeeClass(name=node.name, methods=methods, superclass=superclass)
        self.env.define(node.name, klass)

    def _exec_IfStmt(self, node: IfStmt):
        condition = self._eval(node.condition)
        if pee_truthy(condition):
            self._exec_in_scope(node.then_branch, "if:then")
        elif node.else_branch is not None:
            if isinstance(node.else_branch, IfStmt):
                self._exec(node.else_branch)
            else:
                self._exec_in_scope(node.else_branch, "if:else")

    def _exec_WhileStmt(self, node: WhileStmt):
        while pee_truthy(self._eval(node.condition)):
            try:
                self._exec_in_scope(node.body, "while")
            except BreakSignal:
                break
            except ContinueSignal:
                continue

    def _exec_ForStmt(self, node: ForStmt):
        iterable = self._eval(node.iterable)
        py_iter  = self._to_python_iter(iterable, node.line, node.column)
        for item in py_iter:
            child = self.env.child("for")
            child.define(node.variable, item)
            old_env = self.env
            self.env = child
            try:
                self._exec(node.body)
            except BreakSignal:
                self.env = old_env
                break
            except ContinueSignal:
                self.env = old_env
                continue
            finally:
                self.env = old_env

    def _exec_RepeatStmt(self, node: RepeatStmt):
        count = self._eval(node.count)
        if not isinstance(count, (int, float)):
            raise TaipanTypeError("repeat count must be a number", node.line, node.column)
        for _ in range(int(count)):
            try:
                self._exec_in_scope(node.body, "repeat")
            except BreakSignal:
                break
            except ContinueSignal:
                continue

    def _exec_ReturnStmt(self, node: ReturnStmt):
        value = self._eval(node.value) if node.value is not None else None
        raise ReturnSignal(value)

    def _exec_BreakStmt(self, node: BreakStmt):
        raise BreakSignal()

    def _exec_ContinueStmt(self, node: ContinueStmt):
        raise ContinueSignal()

    def _exec_TryCatchStmt(self, node: TryCatchStmt):
        try:
            self._exec_in_scope(node.try_block, "try")
        except (ReturnSignal, BreakSignal, ContinueSignal):
            raise   # Control-flow signals must propagate
        except (TaipanRuntimeError, TaipanTypeError, TaipanNameError,
                TaipanIndexError, TaipanAttributeError, TaipanValueError,
                TaipanDivisionByZeroError) as e:
            child = self.env.child("catch")
            child.define(node.error_var, e.message if hasattr(e, "message") else str(e))
            old_env = self.env
            self.env = child
            try:
                self._exec(node.catch_block)
            finally:
                self.env = old_env
        except (ReturnSignal, BreakSignal, ContinueSignal):
            raise   # already handled above, double-guard
        except Exception as e:
            # Generic Python exceptions (e.g. ZeroDivisionError from Python layer)
            child = self.env.child("catch")
            child.define(node.error_var, str(e))
            old_env = self.env
            self.env = child
            try:
                self._exec(node.catch_block)
            finally:
                self.env = old_env

    def _exec_ImportStmt(self, node: ImportStmt):
        mod_name = node.module
        alias    = node.alias or mod_name.split(".")[-1]

        # Python interop: import python "module_name"
        if getattr(node, "backend", "taipan") == "python":
            try:
                import importlib
                py_mod = importlib.import_module(mod_name)
                self.env.define(alias, py_mod)
            except ImportError as e:
                raise TaipanRuntimeError(
                    f"Cannot import Python module '{mod_name}': {e}",
                    node.line, node.column
                )
            return

        # 1. stdlib
        module = _load_stdlib_module(mod_name)
        if module is not None:
            self.env.define(alias, module)
            return

        # 2. User .pk file
        pk_mod = self._load_pk_module(mod_name, node.line, node.column)
        if pk_mod is not None:
            self.env.define(alias, pk_mod)
            return

        # 3. Python module (fallback)
        try:
            import importlib
            py_mod = importlib.import_module(mod_name)
            self.env.define(alias, py_mod)
        except ImportError:
            raise TaipanRuntimeError(
                f"Cannot find module '{mod_name}'. "
                f"Install it with: tpkg install {mod_name}",
                node.line, node.column
            )

    def _load_pk_module(self, mod_name: str, line: int, col: int):
        """Resolve a module name to a .tp file and load it."""
        rel_path = mod_name.replace(".", os.sep) + ".tp"
        search_dirs = []
        if self.filename and self.filename not in ("<stdin>", "<repl>"):
            search_dirs.append(os.path.dirname(os.path.abspath(self.filename)))
        search_dirs.append(os.getcwd())

        for search_dir in search_dirs:
            full_path = os.path.join(search_dir, rel_path)
            if os.path.isfile(full_path):
                return self._exec_pk_file_as_module(full_path, mod_name, line, col)
        return None

    def _exec_pk_file_as_module(self, filepath: str, mod_name: str, line: int, col: int) -> PeeMap:
        """Execute a .pk file in isolation and return its public names as a PeeMap."""
        real_path = os.path.realpath(filepath)
        if real_path in self._module_cache:
            return self._module_cache[real_path]

        try:
            source = open(filepath, "r", encoding="utf-8").read()
        except IOError as exc:
            raise TaipanRuntimeError(f"Cannot read module '{mod_name}': {exc}", line, col)

        from taipan.compiler.lexer.lexer import Lexer as _Lex
        from taipan.compiler.parser.parser import Parser as _Par
        try:
            tokens = _Lex(source, filepath).tokenize()
            ast    = _Par(tokens, filepath).parse()
        except Exception as exc:
            raise TaipanRuntimeError(f"Error parsing module '{mod_name}': {exc}", line, col)

        sub = Interpreter(filename=filepath)
        sub._module_cache = self._module_cache  # share cache to prevent cycles
        try:
            sub.execute(ast)
        except Exception as exc:
            raise TaipanRuntimeError(f"Error in module '{mod_name}': {exc}", line, col)

        # Collect names defined by the module (exclude built-ins)
        fresh = Interpreter()
        builtin_names = set(fresh.globals._vars.keys())
        mod_data = {
            k: v for k, v in sub.globals._vars.items()
            if k not in builtin_names
        }
        result = PeeMap(mod_data)
        self._module_cache[real_path] = result
        return result

    def _exec_SpawnStmt(self, node: SpawnStmt):
        # Capture the spawning thread's environment at spawn time so the
        # child thread starts from the same lexical scope without sharing
        # the same pointer (mutations in child don't affect parent).
        parent_env = self.env

        def run():
            # Initialize thread-local env for this new thread via the property.
            self.env = parent_env
            try:
                self._eval(node.expression)
            except Exception:
                pass

        t = threading.Thread(target=run, daemon=True)
        with self._threads_lock:
            self._threads.append(t)
        t.start()

    def _exec_WaitStmt(self, node: WaitStmt):
        with self._threads_lock:
            threads = list(self._threads)
        for t in threads:
            t.join()
        with self._threads_lock:
            self._threads.clear()

    def _exec_AiDeclStmt(self, node: AiDeclStmt):
        ai_instance = PeeAI(name=node.name)
        self.env.define(node.name, ai_instance)

    def _exec_TestStmt(self, node: TestStmt):
        """Execute a test block: catch errors, record pass/fail."""
        import traceback
        old_env = self.env
        child = old_env.child("test:" + node.name)
        self.env = child
        try:
            self._exec(node.body)
            self._test_results.append({"name": node.name, "passed": True, "error": None})
        except Exception as exc:
            self._test_results.append({"name": node.name, "passed": False, "error": str(exc)})
        finally:
            self.env = old_env

    def _exec_MatchStmt(self, node: MatchStmt):
        """Execute a match/switch statement."""
        subject = self._eval(node.subject)
        for case in node.cases:
            pattern = self._eval(case.pattern)
            if self._pee_eq(subject, pattern):
                self._exec_in_scope(case.body, "match:case")
                return
        if node.default:
            self._exec_in_scope(node.default, "match:default")

    # ── Expression evaluators ─────────────────────────────────────────────────

    def _eval_IntLiteral(self, node: IntLiteral)       -> int:   return node.value
    def _eval_FloatLiteral(self, node: FloatLiteral)   -> float: return node.value
    def _eval_StringLiteral(self, node: StringLiteral) -> str:   return node.value
    def _eval_BoolLiteral(self, node: BoolLiteral)     -> bool:  return node.value
    def _eval_NullLiteral(self, node: NullLiteral)              -> None: return None

    def _eval_Identifier(self, node: Identifier) -> Any:
        return self.env.get(node.name, node.line, node.column)

    def _eval_ListLiteral(self, node: ListLiteral) -> PeeList:
        return PeeList([self._eval(e) for e in node.elements])

    def _eval_MapLiteral(self, node: MapLiteral) -> PeeMap:
        d = {}
        for k_node, v_node in node.pairs:
            k = self._eval(k_node)
            v = self._eval(v_node)
            d[k] = v
        return PeeMap(d)

    def _eval_SetLiteral(self, node: SetLiteral) -> PeeSet:
        return PeeSet([self._eval(e) for e in node.elements])

    def _eval_TupleLiteral(self, node: TupleLiteral) -> PeeTuple:
        return PeeTuple([self._eval(e) for e in node.elements])

    def _eval_RangeExpr(self, node: RangeExpr) -> PeeRange:
        start = self._eval(node.start)
        end   = self._eval(node.end)
        step  = self._eval(node.step) if node.step else 1
        return PeeRange(int(start), int(end), int(step), node.inclusive)

    def _eval_UnaryExpr(self, node: UnaryExpr) -> Any:
        val = self._eval(node.operand)
        match node.operator:
            case "-":
                if isinstance(val, (int, float)):
                    return -val
                raise TaipanTypeError(f"Cannot negate {type(val).__name__}", node.line, node.column)
            case "!" | "not":
                return not pee_truthy(val)
            case _:
                raise TaipanRuntimeError(f"Unknown unary operator '{node.operator}'", node.line, node.column)

    def _eval_BinaryExpr(self, node: BinaryExpr) -> Any:
        # Short-circuit logical ops
        if node.operator == "and":
            left = self._eval(node.left)
            return left if not pee_truthy(left) else self._eval(node.right)
        if node.operator == "or":
            left = self._eval(node.left)
            return left if pee_truthy(left) else self._eval(node.right)

        left  = self._eval(node.left)
        right = self._eval(node.right)
        return self._apply_binary(left, node.operator, right, node.line, node.column)

    def _apply_binary(self, left: Any, op: str, right: Any, line: int, col: int) -> Any:
        try:
            match op:
                case "+":
                    if isinstance(left, str) or isinstance(right, str):
                        return pee_str(left) + pee_str(right)
                    if isinstance(left, PeeList) and isinstance(right, PeeList):
                        return left + right
                    return left + right
                case "-":  return left - right
                case "*":
                    if isinstance(left, str) and isinstance(right, int):
                        return left * right
                    return left * right
                case "/":
                    if right == 0:
                        raise TaipanDivisionByZeroError(line, col)
                    return left / right
                case "//":
                    if right == 0:
                        raise TaipanDivisionByZeroError(line, col)
                    return left // right
                case "%":  return left % right
                case "**": return left ** right
                case "==": return self._pee_eq(left, right)
                case "!=": return not self._pee_eq(left, right)
                case "<":  return left < right
                case "<=": return left <= right
                case ">":  return left > right
                case ">=": return left >= right
                case "in":
                    if isinstance(right, (PeeList, PeeMap, PeeSet, PeeTuple, PeeRange, str)):
                        return left in right
                    raise TaipanTypeError(f"'in' requires a collection, got {type(right).__name__}", line, col)
                case _:
                    raise TaipanRuntimeError(f"Unknown operator '{op}'", line, col)
        except (TypeError, AttributeError) as e:
            raise TaipanTypeError(
                f"Operator '{op}' cannot be applied to {type(left).__name__} and {type(right).__name__}: {e}",
                line, col
            )

    def _pee_eq(self, a: Any, b: Any) -> bool:
        if type(a) != type(b):
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                return a == b
            return False
        return a == b

    def _eval_CallExpr(self, node: CallExpr) -> Any:
        callee = self._eval(node.callee)
        args   = [self._eval(a) for a in node.arguments]
        return self._call(callee, args, node.line, node.column)

    def _call(self, callee: Any, args: list, line: int, col: int) -> Any:
        # Built-in Taipan function
        if isinstance(callee, PeeFunction):
            if callee.is_builtin:
                return callee.builtin_fn(args)
            if callee.is_async:
                return PeePromise(self._call_function, callee, args, line, col)
            return self._call_function(callee, args, line, col)

        # Bound method
        if isinstance(callee, BoundMethod):
            if callee.method.is_async:
                return PeePromise(self._call_method, callee.instance, callee.method, args, line, col)
            return self._call_method(callee.instance, callee.method, args, line, col)

        # Class instantiation
        if isinstance(callee, PeeClass):
            return self._instantiate(callee, args, line, col)

        # PeeMap used as a module (stdlib)
        if isinstance(callee, PeeMap):
            raise TaipanTypeError("PeeMap is not callable", line, col)

        # Python callable (stdlib module functions)
        if callable(callee):
            return callee(args)

        raise TaipanTypeError(
            f"'{pee_str(callee)}' ({type(callee).__name__}) is not callable",
            line, col
        )

    def _eval_AwaitExpr(self, node: AwaitExpr) -> Any:
        val = self._eval(node.expression)
        if isinstance(val, PeePromise):
            try:
                return val.wait()
            except Exception as e:
                if isinstance(e, TaipanRuntimeError):
                    raise e
                raise TaipanRuntimeError(str(e), node.line, node.column)
        return val

    def _exec_AwaitExpr(self, node: AwaitExpr) -> Any:
        return self._eval_AwaitExpr(node)

    def _eval_LambdaExpr(self, node: LambdaExpr) -> PeeFunction:
        """Create a PeeFunction from a lambda expression."""
        return PeeFunction(
            name="<lambda>",
            params=node.params,
            body=node.body,   # may be an expression (not a Block)
            closure=self.env,
        )

    def _call_function(self, fn: PeeFunction, args: list, line: int, col: int) -> Any:
        # Bind arguments to parameters
        child = fn.closure.child(f"func:{fn.name}")

        for i, param in enumerate(fn.params):
            if i < len(args):
                child.define(param.name, args[i])
            elif param.default is not None:
                child.define(param.name, self._eval(param.default))
            else:
                raise TaipanRuntimeError(
                    f"Missing argument '{param.name}' for function '{fn.name}'",
                    line, col
                )

        old_env = self.env
        self.env = child
        try:
            # Lambda bodies are single expressions; Block bodies are executed
            if isinstance(fn.body, Block):
                self._exec(fn.body)
                return None
            else:
                return self._eval(fn.body)
        except ReturnSignal as r:
            return r.value
        finally:
            self.env = old_env

    def _call_method(self, instance: PeeInstance, method: PeeFunction,
                      args: list, line: int, col: int) -> Any:
        child = method.closure.child(f"method:{method.name}")
        child.define("self", instance)

        for i, param in enumerate(method.params):
            if param.name == "self":
                continue
            actual_i = i  # params may or may not include 'self'
            if i < len(args):
                child.define(param.name, args[i])
            elif param.default is not None:
                child.define(param.name, self._eval(param.default))
            else:
                raise TaipanRuntimeError(
                    f"Missing argument '{param.name}' for method '{method.name}'",
                    line, col
                )

        old_env = self.env
        self.env = child
        try:
            self._exec(method.body)
            return None
        except ReturnSignal as r:
            return r.value
        finally:
            self.env = old_env

    def _instantiate(self, klass: PeeClass, args: list, line: int, col: int) -> PeeInstance:
        instance = PeeInstance(klass)
        init = klass.find_method("init") or klass.find_method("__init__")
        if init:
            self._call_method(instance, init, args, line, col)
        return instance

    def _eval_MemberExpr(self, node: MemberExpr) -> Any:
        obj  = self._eval(node.object)
        prop = node.property

        if isinstance(obj, PeeInstance):
            try:
                return obj.get(prop)
            except AttributeError as e:
                raise TaipanAttributeError(str(e), node.line, node.column)

        # For PeeMap (stdlib modules, user maps): check _data first
        if isinstance(obj, PeeMap):
            if prop in obj._data:
                return obj._data[prop]
            raise TaipanAttributeError(f"Map has no attribute '{prop}'", node.line, node.column)

        if isinstance(obj, (PeeList, PeeSet, PeeTuple)):
            # Check attribute first (like .length)
            try:
                return obj.pee_attr(prop)
            except AttributeError:
                pass
            # Return a bound callable for methods
            def method_proxy(args, _obj=obj, _prop=prop):
                return _obj.pee_method(_prop, args)
            return PeeFunction(
                name=prop, params=[], body=None, closure=self.env,
                is_builtin=True, builtin_fn=method_proxy
            )

        if isinstance(obj, PeeAI):
            def ai_method(args, _prop=prop, _obj=obj):
                return _obj.pee_method(_prop, args)
            return PeeFunction(
                name=prop, params=[], body=None, closure=self.env,
                is_builtin=True, builtin_fn=ai_method
            )

        # Stdlib module (stored as a dict-like PeeMap)
        if isinstance(obj, dict):
            if prop in obj:
                return obj[prop]

        # Custom Taipan-compatible objects (Stack, Queue, etc.) with pee_method
        if hasattr(obj, "pee_method"):
            def pee_meth(args, _obj=obj, _prop=prop):
                return _obj.pee_method(_prop, args)
            return PeeFunction(
                name=prop, params=[], body=None, closure=self.env,
                is_builtin=True, builtin_fn=pee_meth
            )

        # Python object (stdlib)
        if hasattr(obj, prop):
            attr = getattr(obj, prop)
            if callable(attr):
                def py_method(args, _attr=attr):
                    return _attr(*args)
                return PeeFunction(
                    name=prop, params=[], body=None, closure=self.env,
                    is_builtin=True, builtin_fn=py_method
                )
            return attr

        raise TaipanAttributeError(
            f"Object of type '{type(obj).__name__}' has no attribute '{prop}'",
            node.line, node.column
        )

    def _eval_IndexExpr(self, node: IndexExpr) -> Any:
        obj = self._eval(node.object)
        idx = self._eval(node.index)

        def _to_int_idx(idx_val, kind: str) -> int:
            """Convert index to int, raising a clear TaipanTypeError on failure."""
            if isinstance(idx_val, bool):
                # bool is a subtype of int in Python, allow it
                return int(idx_val)
            if isinstance(idx_val, (int, float)):
                return int(idx_val)
            raise TaipanTypeError(
                f"{kind} index must be an Int, got {type(idx_val).__name__} ({idx_val!r})",
                node.line, node.column
            )

        if isinstance(obj, PeeList):
            i = _to_int_idx(idx, "List")
            try:
                return obj[i]
            except IndexError:
                raise TaipanIndexError(f"List index {i} out of range", node.line, node.column)

        if isinstance(obj, PeeMap):
            if idx not in obj:
                raise TaipanAttributeError(f"Map has no key '{idx}'", node.line, node.column)
            return obj[idx]

        if isinstance(obj, PeeTuple):
            i = _to_int_idx(idx, "Tuple")
            try:
                return obj[i]
            except IndexError:
                raise TaipanIndexError(f"Tuple index {i} out of range", node.line, node.column)

        if isinstance(obj, str):
            i = _to_int_idx(idx, "String")
            try:
                return obj[i]
            except IndexError:
                raise TaipanIndexError(f"String index {i} out of range", node.line, node.column)

        raise TaipanTypeError(
            f"Type '{type(obj).__name__}' does not support indexing", node.line, node.column
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _exec_in_scope(self, block: Block, scope_name: str):
        child = self.env.child(scope_name)
        old   = self.env
        self.env = child
        try:
            self._exec(block)
        finally:
            self.env = old

    def _to_python_iter(self, val: Any, line: int, col: int):
        if isinstance(val, (PeeList, PeeSet, PeeTuple, PeeRange, str)):
            return iter(val)
        if isinstance(val, PeeMap):
            return iter(val._data.keys())
        raise TaipanTypeError(
            f"Cannot iterate over {type(val).__name__}", line, col
        )
