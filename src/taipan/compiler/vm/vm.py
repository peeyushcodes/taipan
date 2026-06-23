"""
Taipan Bytecode Virtual Machine
==================================
A stack-based VM that executes Taipan CodeObjects produced by the
BytecodeCompiler. It reuses the same runtime types (PeeList, PeeMap,
PeeFunction, etc.) as the tree-walk interpreter for full compatibility.

Thread safety: Uses threading.local() for the env pointer, same strategy
as the tree-walk interpreter.
"""

from __future__ import annotations
import threading
import os
from typing import Any, List, Optional

from taipan.compiler.vm.instructions import Opcode, Instruction, CodeObject, _MISSING
from taipan.runtime.environment import Environment
from taipan.runtime.errors import (
    TaipanRuntimeError, TaipanTypeError, TaipanNameError,
    TaipanIndexError, TaipanAttributeError, TaipanValueError,
    TaipanDivisionByZeroError, ReturnSignal, BreakSignal, ContinueSignal,
)
from taipan.runtime.taipan_types import (
    PeeList, PeeMap, PeeSet, PeeTuple, PeeRange,
    PeeFunction, PeeClass, PeeInstance, BoundMethod, PeeAI,
    pee_str, pee_truthy,
)


# ── Handler record ─────────────────────────────────────────────────────────────

class _Handler:
    """An active try/catch handler on the handler stack."""
    def __init__(self, catch_ip: int, error_var: str):
        self.catch_ip  = catch_ip
        self.error_var = error_var


# ── VM ────────────────────────────────────────────────────────────────────────

class VM:
    """
    Stack-based virtual machine for Taipan.

    Usage:
        vm = VM()
        vm.execute(code_object)
    """

    def __init__(self, filename: str = "<vm>"):
        self.filename    = filename
        self.globals     = Environment(name="global")
        self._setup_builtins(self.globals)
        self._tls        = threading.local()
        self._tls.env    = self.globals
        self._threads:   List[threading.Thread] = []
        self._threads_lock = threading.Lock()
        self._module_cache: dict = {}

    # ── Thread-local env property ─────────────────────────────────────────────

    @property
    def env(self) -> Environment:
        tls = self.__dict__.get("_tls")
        if tls is None:
            return self.__dict__.get("globals", None)
        return getattr(tls, "env", self.__dict__.get("globals", None))

    @env.setter
    def env(self, value: Environment):
        tls = self.__dict__.get("_tls")
        if tls is None:
            return
        tls.env = value

    # ── Public API ────────────────────────────────────────────────────────────

    def execute(self, code: CodeObject) -> Any:
        """Execute a top-level CodeObject (module) in the global environment."""
        return self._run_frame(code, self.globals)

    # ── Built-ins ─────────────────────────────────────────────────────────────

    def _setup_builtins(self, env: Environment):
        """Mirror the tree-walk interpreter's built-in set."""
        from taipan.compiler.backend.interpreter import Interpreter as _TW
        # Spin up a tree-walk interpreter just to steal its builtins env
        tw = _TW()
        for name, val in tw.globals._vars.items():
            env.define(name, val)

    # ── Frame execution ───────────────────────────────────────────────────────

    def _run_frame(self, code: CodeObject, env: Environment) -> Any:
        """Execute a CodeObject in the given environment, returning a value."""
        stack:   List[Any]      = []
        ip:      int            = 0
        handlers: List[_Handler] = []   # exception handler stack
        instrs   = code.instructions
        n        = len(instrs)

        while ip < n:
            instr = instrs[ip]
            ip += 1

            try:
                result = self._step(instr, stack, code, env, handlers)
                if result is _RETURN_SENTINEL:
                    return stack.pop() if stack else None
                if isinstance(result, _JumpTo):
                    ip = result.target

            except (TaipanRuntimeError, TaipanTypeError, TaipanNameError,
                    TaipanIndexError, TaipanAttributeError, TaipanValueError,
                    TaipanDivisionByZeroError) as exc:
                if handlers:
                    h = handlers.pop()
                    # Push error message for the catch body to consume
                    stack.append(exc.message if hasattr(exc, "message") else str(exc))
                    ip = h.catch_ip
                else:
                    raise

            except Exception as exc:
                # Generic Python exceptions inside Taipan code
                if handlers:
                    h = handlers.pop()
                    stack.append(str(exc))
                    ip = h.catch_ip
                else:
                    raise

        return None

    def _step(self, instr: Instruction, stack: list,
              code: CodeObject, env: Environment,
              handlers: list) -> Any:
        """Execute a single instruction. Returns _RETURN_SENTINEL or _JumpTo or None."""
        op  = instr.opcode
        arg = instr.arg

        match op:
            # ── Constants & names ────────────────────────────────────────────
            case Opcode.LOAD_CONST:
                stack.append(code.constants[arg])

            case Opcode.LOAD_NAME:
                stack.append(env.get(code.names[arg], 0, 0))

            case Opcode.DEFINE_NAME:
                env.define(code.names[arg], stack.pop())

            case Opcode.DEFINE_CONST:
                env.define(code.names[arg], stack.pop(), constant=True)

            case Opcode.STORE_NAME:
                val = stack.pop()
                name = code.names[arg]
                try:
                    env.set(name, val, 0, 0)
                except TaipanNameError:
                    env.define(name, val)

            case Opcode.DELETE_NAME:
                env.delete(code.names[arg], 0, 0) if hasattr(env, "delete") else None

            # ── Stack ops ────────────────────────────────────────────────────
            case Opcode.POP_TOP:
                if stack:
                    stack.pop()

            case Opcode.DUP_TOP:
                stack.append(stack[-1])

            # ── Attributes & indexing ─────────────────────────────────────────
            case Opcode.LOAD_ATTR:
                obj  = stack.pop()
                klass = obj.klass if isinstance(obj, PeeInstance) else type(obj)
                if instr.cache_class is klass:
                    if instr.cache_is_method:
                        if klass is type(obj):
                            stack.append(instr.cache_val(obj))
                        else:
                            stack.append(BoundMethod(obj, instr.cache_val))
                    elif isinstance(obj, PeeInstance):
                        prop = code.names[arg]
                        if prop in obj.fields:
                            stack.append(obj.fields[prop])
                        else:
                            stack.append(self._get_attr(obj, prop, 0, 0))
                    else:
                        stack.append(self._get_attr(obj, code.names[arg], 0, 0))
                else:
                    prop = code.names[arg]
                    val = self._get_attr(obj, prop, 0, 0)
                    stack.append(val)
                    
                    # Populate inline cache
                    instr.cache_class = klass
                    if isinstance(obj, PeeInstance):
                        method = obj.klass.find_method(prop)
                        if method is not None:
                            instr.cache_is_method = True
                            instr.cache_val = method
                        else:
                            instr.cache_is_method = False
                    else:
                        if isinstance(val, PeeFunction) and val.is_builtin:
                            instr.cache_is_method = True
                            if isinstance(obj, (PeeList, PeeSet, PeeTuple)):
                                instr.cache_val = lambda o, p=prop: PeeFunction(
                                    name=p, params=[], body=None, closure=self.globals,
                                    is_builtin=True, builtin_fn=lambda args, _o=o, _p=p: _o.pee_method(_p, args)
                                )
                            elif isinstance(obj, PeeAI):
                                instr.cache_val = lambda o, p=prop: PeeFunction(
                                    name=p, params=[], body=None, closure=self.globals,
                                    is_builtin=True, builtin_fn=lambda args, _o=o, _p=p: _o.pee_method(_p, args)
                                )
                            else:
                                instr.cache_val = lambda o, p=prop: PeeFunction(
                                    name=p, params=[], body=None, closure=self.globals,
                                    is_builtin=True, builtin_fn=lambda args, _attr=getattr(o, p): _attr(*args)
                                )
                        else:
                            instr.cache_is_method = False

            case Opcode.STORE_ATTR:
                obj  = stack.pop()
                val  = stack.pop()
                prop = code.names[arg]
                self._set_attr(obj, prop, val, 0, 0)

            case Opcode.LOAD_INDEX:
                idx = stack.pop()
                obj = stack.pop()
                stack.append(self._get_index(obj, idx, 0, 0))

            case Opcode.STORE_INDEX:
                idx = stack.pop()
                obj = stack.pop()
                val = stack.pop()
                self._set_index(obj, idx, val, 0, 0)

            # ── Operators ────────────────────────────────────────────────────
            case Opcode.BINARY_OP:
                right = stack.pop()
                left  = stack.pop()
                op_str = code.names[arg]
                stack.append(self._apply_binary(left, op_str, right, 0, 0))

            case Opcode.UNARY_OP:
                val    = stack.pop()
                op_str = code.names[arg]
                if op_str == "-":
                    stack.append(-val)
                elif op_str in ("!", "not"):
                    stack.append(not pee_truthy(val))
                else:
                    raise TaipanRuntimeError(f"Unknown unary operator '{op_str}'")

            # ── Jumps ────────────────────────────────────────────────────────
            case Opcode.JUMP:
                return _JumpTo(arg)

            case Opcode.JUMP_IF_FALSE:
                cond = stack.pop()
                if not pee_truthy(cond):
                    return _JumpTo(arg)

            case Opcode.JUMP_IF_TRUE:
                cond = stack.pop()
                if pee_truthy(cond):
                    return _JumpTo(arg)

            case Opcode.JUMP_IF_FALSE_PEEK:
                if not pee_truthy(stack[-1]):
                    return _JumpTo(arg)

            case Opcode.JUMP_IF_TRUE_PEEK:
                if pee_truthy(stack[-1]):
                    return _JumpTo(arg)


            # ── Iteration ────────────────────────────────────────────────────
            case Opcode.GET_ITER:
                val = stack.pop()
                stack.append(iter(self._to_iter(val, 0, 0)))

            case Opcode.FOR_ITER:
                it = stack.pop()   # pop iterator
                try:
                    item = next(it)
                    stack.append(item)
                    # Put iterator back via STORE_NAME (handled by compiler:
                    # iter was in a named local, we just used LOAD_NAME to get it,
                    # so we need to put it back in env)
                    # BUT: The compiler stored it via DEFINE_NAME, so env still has it.
                    # We just need to update the env with the (same) iterator object.
                    # Since Python iterators mutate in-place, this is automatic —
                    # env still holds the same iterator object, which was advanced.
                except StopIteration:
                    return _JumpTo(arg)

            # ── Collections ─────────────────────────────────────────────────
            case Opcode.BUILD_LIST:
                items = stack[-arg:] if arg > 0 else []
                if arg > 0:
                    del stack[-arg:]
                stack.append(PeeList(items))

            case Opcode.BUILD_MAP:
                pairs = stack[-(arg * 2):] if arg > 0 else []
                if arg > 0:
                    del stack[-(arg * 2):]
                d = {}
                for i in range(0, len(pairs), 2):
                    d[pairs[i]] = pairs[i + 1]
                stack.append(PeeMap(d))

            case Opcode.BUILD_TUPLE:
                items = stack[-arg:] if arg > 0 else []
                if arg > 0:
                    del stack[-arg:]
                stack.append(PeeTuple(items))

            case Opcode.BUILD_SET:
                items = stack[-arg:] if arg > 0 else []
                if arg > 0:
                    del stack[-arg:]
                stack.append(PeeSet(items))

            case Opcode.BUILD_RANGE:
                if arg == 1:
                    step  = stack.pop()
                    end   = stack.pop()
                    start = stack.pop()
                    stack.append(PeeRange(int(start), int(end), int(step), False))
                else:
                    end   = stack.pop()
                    start = stack.pop()
                    stack.append(PeeRange(int(start), int(end), 1, False))

            # ── Functions & classes ──────────────────────────────────────────
            case Opcode.MAKE_FUNCTION:
                func_code = stack.pop()           # CodeObject from constants
                fname     = code.names[arg]

                # Evaluate default values in current env
                defaults = []
                for d in func_code.defaults:
                    if d is _MISSING:
                        defaults.append(_MISSING)
                    elif isinstance(d, CodeObject):
                        val = self._run_frame(d, env)
                        defaults.append(val)
                    else:
                        defaults.append(d)

                # Build Param-like objects (lightweight tuples)
                from taipan.compiler.ast.nodes import Param
                params = []
                for i, pname in enumerate(func_code.params):
                    dval = defaults[i] if i < len(defaults) else _MISSING
                    # Store default as a ConstLiteral-like trick: we just pass
                    # the value through vm_defaults
                    params.append(Param(name=pname, line=0, column=0))

                fn = PeeFunction(
                    name=fname,
                    params=params,
                    body=None,          # VM mode: body is in code_obj
                    closure=env,
                    is_builtin=False,
                    is_method=False,
                )
                fn._vm_code     = func_code   # type: ignore[attr-defined]
                fn._vm_defaults = defaults    # type: ignore[attr-defined]
                stack.append(fn)

            case Opcode.CALL:
                n_args = arg
                args   = stack[-n_args:] if n_args > 0 else []
                if n_args > 0:
                    del stack[-n_args:]
                callee = stack.pop()
                result = self._call(callee, args, 0, 0)
                stack.append(result)

            case Opcode.RETURN:
                return _RETURN_SENTINEL

            case Opcode.BUILD_CLASS:
                # Stack: superclass, [method_name, PeeFunction, ...], count
                count = stack.pop()
                methods = {}
                for _ in range(count):
                    fn_obj   = stack.pop()
                    fn_name  = stack.pop()
                    if isinstance(fn_obj, PeeFunction):
                        fn_obj.is_method = True
                    methods[fn_name] = fn_obj

                superclass = stack.pop()
                if superclass is None:
                    superclass = None
                elif not isinstance(superclass, PeeClass):
                    raise TaipanTypeError(
                        f"'{superclass}' is not a class", 0, 0
                    )

                klass = PeeClass(
                    name=code.names[arg],
                    methods=methods,
                    superclass=superclass,
                )
                stack.append(klass)

            # ── Exception handling ──────────────────────────────────────────
            case Opcode.SETUP_EXCEPT:
                # TOS was pushed before this instr: it's the var name (string constant)
                error_var = stack.pop()
                handlers.append(_Handler(catch_ip=arg, error_var=error_var))

            case Opcode.POP_EXCEPT:
                if handlers:
                    handlers.pop()

            case Opcode.RAISE:
                msg = pee_str(stack.pop())
                raise TaipanRuntimeError(msg, 0, 0)

            # ── Misc ────────────────────────────────────────────────────────
            case Opcode.IMPORT:
                mod_name = code.names[arg]
                result   = self._do_import(mod_name, env)
                stack.append(result)

            case Opcode.SPAWN:
                expr_fn = stack.pop()
                parent_env = env
                def _run(fn=expr_fn, e=parent_env):
                    self.env = e
                    try:
                        self._call(fn, [], 0, 0)
                    except Exception:
                        pass
                t = threading.Thread(target=_run, daemon=True)
                with self._threads_lock:
                    self._threads.append(t)
                t.start()

            case Opcode.WAIT:
                with self._threads_lock:
                    threads = list(self._threads)
                for t in threads:
                    t.join()
                with self._threads_lock:
                    self._threads.clear()

            case Opcode.DEFINE_AI:
                name = code.names[arg]
                ai   = PeeAI(name=name)
                env.define(name, ai)

            case Opcode.NOP:
                pass

            case _:
                raise TaipanRuntimeError(f"Unknown opcode: {op}", 0, 0)

        return None   # normal instruction, continue

    # ── Attribute & index helpers ──────────────────────────────────────────────

    def _get_attr(self, obj: Any, prop: str, line: int, col: int) -> Any:
        if isinstance(obj, PeeInstance):
            try:
                return obj.get(prop)
            except AttributeError as e:
                raise TaipanAttributeError(str(e), line, col)
        if isinstance(obj, PeeMap):
            if prop in obj._data:
                return obj._data[prop]
            raise TaipanAttributeError(f"Map has no attribute '{prop}'", line, col)
        if isinstance(obj, (PeeList, PeeSet, PeeTuple)):
            try:
                return obj.pee_attr(prop)
            except AttributeError:
                def method_proxy(args, _o=obj, _p=prop):
                    return _o.pee_method(_p, args)
                return PeeFunction(name=prop, params=[], body=None, closure=self.globals,
                                   is_builtin=True, builtin_fn=method_proxy)
        if isinstance(obj, PeeAI):
            def ai_method(args, _p=prop, _o=obj):
                return _o.pee_method(_p, args)
            return PeeFunction(name=prop, params=[], body=None, closure=self.globals,
                               is_builtin=True, builtin_fn=ai_method)
        if isinstance(obj, dict):
            if prop in obj:
                return obj[prop]

        if hasattr(obj, "pee_method"):
            def pee_meth(args, _obj=obj, _prop=prop):
                return _obj.pee_method(_prop, args)
            return PeeFunction(
                name=prop, params=[], body=None, closure=self.globals,
                is_builtin=True, builtin_fn=pee_meth
            )

        if hasattr(obj, prop):
            attr = getattr(obj, prop)
            if callable(attr):
                def py_method(args, _attr=attr):
                    return _attr(*args)
                return PeeFunction(
                    name=prop, params=[], body=None, closure=self.globals,
                    is_builtin=True, builtin_fn=py_method
                )
            return attr

        raise TaipanAttributeError(
            f"Cannot get attribute '{prop}' on {type(obj).__name__}", line, col
        )


    def _set_attr(self, obj: Any, prop: str, val: Any, line: int, col: int):
        if isinstance(obj, PeeInstance):
            obj.set(prop, val)
        elif isinstance(obj, PeeMap):
            obj[prop] = val
        else:
            raise TaipanAttributeError(
                f"Cannot set attribute '{prop}' on {type(obj).__name__}", line, col
            )

    def _get_index(self, obj: Any, idx: Any, line: int, col: int) -> Any:
        def _int(i, kind):
            if isinstance(i, bool):
                return int(i)
            if isinstance(i, (int, float)):
                return int(i)
            raise TaipanTypeError(
                f"{kind} index must be an Int, got {type(i).__name__} ({i!r})", line, col
            )
        if isinstance(obj, PeeList):
            i = _int(idx, "List")
            try:
                return obj[i]
            except IndexError:
                raise TaipanIndexError(f"List index {i} out of range", line, col)
        if isinstance(obj, PeeMap):
            if idx not in obj:
                raise TaipanAttributeError(f"Map has no key '{idx}'", line, col)
            return obj[idx]
        if isinstance(obj, PeeTuple):
            i = _int(idx, "Tuple")
            try:
                return obj[i]
            except IndexError:
                raise TaipanIndexError(f"Tuple index {i} out of range", line, col)
        if isinstance(obj, str):
            i = _int(idx, "String")
            try:
                return obj[i]
            except IndexError:
                raise TaipanIndexError(f"String index {i} out of range", line, col)
        raise TaipanTypeError(
            f"Type '{type(obj).__name__}' does not support indexing", line, col
        )

    def _set_index(self, obj: Any, idx: Any, val: Any, line: int, col: int):
        if isinstance(obj, PeeList):
            try:
                obj[int(idx)] = val
            except IndexError:
                raise TaipanIndexError(f"List index {idx} out of range", line, col)
        elif isinstance(obj, PeeMap):
            obj[idx] = val
        else:
            raise TaipanTypeError(
                f"Cannot index-assign into {type(obj).__name__}", line, col
            )

    # ── Binary / unary operators ──────────────────────────────────────────────

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
                    raise TaipanTypeError(
                        f"'in' requires a collection, got {type(right).__name__}", line, col
                    )
                case _:
                    raise TaipanRuntimeError(f"Unknown operator '{op}'", line, col)
        except (TypeError, AttributeError) as e:
            raise TaipanTypeError(
                f"Operator '{op}' cannot be applied to "
                f"{type(left).__name__} and {type(right).__name__}: {e}", line, col
            )

    def _pee_eq(self, a: Any, b: Any) -> bool:
        if type(a) != type(b):
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                return a == b
            return False
        return a == b

    # ── Calling functions ──────────────────────────────────────────────────────

    def _call(self, callee: Any, args: list, line: int, col: int) -> Any:
        if isinstance(callee, PeeFunction):
            if callee.is_builtin:
                return callee.builtin_fn(args)
            return self._call_pee_function(callee, args, line, col)

        if isinstance(callee, BoundMethod):
            return self._call_bound_method(callee, args, line, col)

        if isinstance(callee, PeeClass):
            return self._instantiate(callee, args, line, col)

        if callable(callee):
            return callee(args)

        raise TaipanTypeError(
            f"'{pee_str(callee)}' ({type(callee).__name__}) is not callable", line, col
        )

    def _call_pee_function(self, fn: PeeFunction, args: list, line: int, col: int) -> Any:
        # Check if this function has a VM code object (compiled mode)
        vm_code = getattr(fn, "_vm_code", None)
        if vm_code is not None:
            child = fn.closure.child(f"func:{fn.name}")
            self._bind_args(fn, args, child, line, col, vm_code=vm_code)
            return self._run_frame(vm_code, child)

        # Fallback: run through tree-walk interpreter (e.g., closures from mixed mode)
        from taipan.compiler.backend.interpreter import Interpreter as _TW
        tw = _TW.__new__(_TW)
        tw.filename = self.filename
        tw._threads = self._threads
        tw._threads_lock = self._threads_lock
        tw.globals = self.globals
        tw._tls = threading.local()
        tw._tls.env = self.env
        tw._module_cache = self._module_cache
        return tw._call_function(fn, args, line, col)

    def _call_bound_method(self, bm: BoundMethod, args: list, line: int, col: int) -> Any:
        method = bm.method
        vm_code = getattr(method, "_vm_code", None)
        child = method.closure.child(f"method:{method.name}")
        child.define("self", bm.instance)
        self._bind_method_args(method, args, child, line, col, vm_code=vm_code)
        if vm_code:
            return self._run_frame(vm_code, child)
        # fallback to tree-walk
        from taipan.compiler.backend.interpreter import Interpreter as _TW
        tw = _TW.__new__(_TW)
        tw.filename = self.filename
        tw._threads = self._threads
        tw._threads_lock = self._threads_lock
        tw.globals = self.globals
        tw._tls = threading.local()
        tw._tls.env = child
        tw._module_cache = self._module_cache
        old_env = tw.env
        tw.env = child
        try:
            tw._exec(method.body)
            return None
        except ReturnSignal as r:
            return r.value
        finally:
            tw.env = old_env

    def _bind_args(self, fn: PeeFunction, args: list, child: Environment,
                   line: int, col: int, vm_code: CodeObject = None):
        """Bind positional args to parameters in child env."""
        params   = vm_code.params   if vm_code else [p.name for p in fn.params]
        defaults = getattr(fn, "_vm_defaults", [_MISSING] * len(params))

        for i, pname in enumerate(params):
            if i < len(args):
                child.define(pname, args[i])
            elif i < len(defaults) and defaults[i] is not _MISSING:
                child.define(pname, defaults[i])
            else:
                raise TaipanRuntimeError(
                    f"Missing argument '{pname}' for function '{fn.name}'", line, col
                )

    def _bind_method_args(self, method: PeeFunction, args: list, child: Environment,
                          line: int, col: int, vm_code: CodeObject = None):
        """Bind args to method parameters (skipping 'self')."""
        params   = vm_code.params   if vm_code else [p.name for p in method.params]
        defaults = getattr(method, "_vm_defaults", [_MISSING] * len(params))

        arg_idx = 0
        for i, pname in enumerate(params):
            if pname == "self":
                continue
            if arg_idx < len(args):
                child.define(pname, args[arg_idx])
                arg_idx += 1
            elif i < len(defaults) and defaults[i] is not _MISSING:
                child.define(pname, defaults[i])
            else:
                raise TaipanRuntimeError(
                    f"Missing argument '{pname}' for method '{method.name}'", line, col
                )

    def _instantiate(self, klass: PeeClass, args: list, line: int, col: int) -> PeeInstance:
        instance = PeeInstance(klass)
        init = klass.find_method("init") or klass.find_method("__init__")
        if init:
            bm = BoundMethod(instance=instance, method=init)
            self._call_bound_method(bm, args, line, col)
        return instance

    # ── Import ────────────────────────────────────────────────────────────────

    def _do_import(self, mod_name: str, env: Environment) -> Any:
        """Import a module (stdlib → .pk → Python)."""
        # Reuse the tree-walk interpreter's import logic
        from taipan.compiler.backend.interpreter import _load_stdlib_module, Interpreter as _TW
        m = _load_stdlib_module(mod_name)
        if m is not None:
            return m

        # User .pk module
        rel_path = mod_name.replace(".", os.sep) + ".tp"
        search_dirs = []
        if self.filename and self.filename not in ("<vm>", "<stdin>", "<repl>"):
            search_dirs.append(os.path.dirname(os.path.abspath(self.filename)))
        search_dirs.append(os.getcwd())

        for d in search_dirs:
            fp = os.path.join(d, rel_path)
            if os.path.isfile(fp):
                real = os.path.realpath(fp)
                if real in self._module_cache:
                    return self._module_cache[real]
                # Execute via a temporary tree-walk sub-interpreter
                tw = _TW(filename=fp)
                tw._module_cache = self._module_cache
                src = open(fp, "r", encoding="utf-8").read()
                from taipan.compiler.lexer.lexer import Lexer
                from taipan.compiler.parser.parser import Parser
                tokens = Lexer(src, fp).tokenize()
                ast    = Parser(tokens, fp).parse()
                tw.execute(ast)
                fresh_tw = _TW()
                builtin_names = set(fresh_tw.globals._vars.keys())
                mod_data = {k: v for k, v in tw.globals._vars.items()
                            if k not in builtin_names}
                result = PeeMap(mod_data)
                self._module_cache[real] = result
                return result

        # Python fallback
        try:
            import importlib
            return importlib.import_module(mod_name)
        except ImportError:
            raise TaipanRuntimeError(
                f"Cannot find module '{mod_name}'", 0, 0
            )

    # ── Iteration helper ──────────────────────────────────────────────────────

    def _to_iter(self, val: Any, line: int, col: int):
        if isinstance(val, PeeList):
            return iter(val)
        if isinstance(val, PeeRange):
            return iter(val)
        if isinstance(val, PeeSet):
            return iter(val)
        if isinstance(val, PeeTuple):
            return iter(val)
        if isinstance(val, str):
            return iter(val)
        if isinstance(val, PeeMap):
            return iter(val._data.keys())
        raise TaipanTypeError(
            f"'{type(val).__name__}' is not iterable", line, col
        )


# ── Internal sentinel types ────────────────────────────────────────────────────

class _JumpTo:
    __slots__ = ("target",)
    def __init__(self, target: int): self.target = target

_RETURN_SENTINEL = object()
