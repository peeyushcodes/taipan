"""
Taipan JIT Compiler — Native Numeric Compilation
====================================================
Compiles type-annotated Taipan functions to native C for 100-1000x speedup.

Supports:
  - Functions with Int/Float parameter types
  - Integer arithmetic: +, -, *, /, %, **
  - Comparisons: ==, !=, <, <=, >, >=
  - If/else, while loops, for loops over ranges
  - Return statements

Not supported (falls back to interpreter):
  - String operations
  - Collections (List, Map, Set)
  - External function calls
  - Dynamic typing

Usage:
    from taipan.compiler.jit.compiler import JITCompiler
    jit = JITCompiler()
    compiled_fn = jit.compile_function(func_node)
    if compiled_fn:
        # Use compiled function instead of interpreter
        result = compiled_fn(args)
"""
import os
import sys
import subprocess
import tempfile
import ctypes
import hashlib
from pathlib import Path
from typing import Any, Optional, Callable, Dict, Set

from taipan.compiler.ast.nodes import (
    Node, Program, Block, FunctionDecl, Param, ReturnStmt,
    IfStmt, WhileStmt, ForStmt, VariableDecl, ConstDecl, AssignStmt,
    BinaryExpr, UnaryExpr, CallExpr, MemberExpr, IndexExpr,
    Identifier, IntLiteral, FloatLiteral, BoolLiteral, NullLiteral,
    RangeExpr, StringLiteral, ExpressionStmt,
)
from taipan.runtime.errors import TaipanRuntimeError


class JITType:
    """Represents a JIT-compilable type."""
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"


class JITCompiler:
    """JIT compiler for numeric Taipan functions."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or (Path.home() / ".taipan" / "jit_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._cc = self._find_compiler()

    def _find_compiler(self) -> str:
        """Find a C compiler on the system."""
        for cc in ["gcc", "clang", "tcc", "cc"]:
            try:
                subprocess.run([cc, "--version"], capture_output=True, check=True)
                return cc
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue
        return None

    def can_compile(self, func: FunctionDecl) -> bool:
        """Check if a function can be JIT-compiled."""
        # Check parameter types
        for p in func.params:
            if p.type_hint not in ("Int", "Float", None):
                return False

        # Check body is compilable
        return self._is_block_compilable(func.body)

    def _is_block_compilable(self, block: Block) -> bool:
        """Check if a block contains only JIT-compilable statements."""
        for stmt in block.statements:
            if not self._is_statement_compilable(stmt):
                return False
        return True

    def _is_statement_compilable(self, stmt: Node) -> bool:
        """Check if a single statement is JIT-compilable."""
        match stmt:
            case ReturnStmt():
                return stmt.value is None or self._is_expr_compilable(stmt.value)
            case IfStmt():
                return (self._is_expr_compilable(stmt.condition)
                        and self._is_block_compilable(stmt.then_branch)
                        and (stmt.else_branch is None or self._is_block_compilable(stmt.else_branch)))
            case WhileStmt():
                return (self._is_expr_compilable(stmt.condition)
                        and self._is_block_compilable(stmt.body))
            case ForStmt():
                return (isinstance(stmt.iterable, RangeExpr)
                        and self._is_expr_compilable(stmt.iterable)
                        and self._is_block_compilable(stmt.body))
            case VariableDecl():
                return stmt.value is None or self._is_expr_compilable(stmt.value)
            case ConstDecl():
                return self._is_expr_compilable(stmt.value)
            case AssignStmt():
                return (isinstance(stmt.target, Identifier)
                        and stmt.operator in ("=", "+=", "-=", "*=", "/=", "%=")
                        and self._is_expr_compilable(stmt.value))
            case ExpressionStmt():
                return self._is_expr_compilable(stmt.expression)
            case _:
                return False

    def _is_expr_compilable(self, expr: Node) -> bool:
        """Check if an expression is JIT-compilable."""
        match expr:
            case IntLiteral() | FloatLiteral() | BoolLiteral() | NullLiteral():
                return True
            case Identifier():
                return True
            case BinaryExpr():
                return (expr.operator in ("+", "-", "*", "/", "%", "**",
                                           "==", "!=", "<", "<=", ">", ">=", "and", "or")
                        and self._is_expr_compilable(expr.left)
                        and self._is_expr_compilable(expr.right))
            case UnaryExpr():
                return (expr.operator in ("-", "!", "not")
                        and self._is_expr_compilable(expr.operand))
            case RangeExpr():
                return (self._is_expr_compilable(expr.start)
                        and self._is_expr_compilable(expr.end)
                        and (expr.step is None or self._is_expr_compilable(expr.step)))
            case CallExpr():
                # Only allow calls to other compiled functions or built-in math
                return False  # For now, no calls
            case MemberExpr() | IndexExpr() | StringLiteral() | ListLiteral() | MapLiteral() | SetLiteral() | TupleLiteral() | LambdaExpr() | FStringLiteral():
                return False
            case _:
                return False

    def compile_function(self, func: FunctionDecl) -> Optional[Callable]:
        """Compile a Taipan function to a native shared library."""
        if not self.can_compile(func):
            return None
        if not self._cc:
            return None

        # Generate C code
        c_code = self._generate_c(func)

        # Cache key based on function source hash
        source_hash = hashlib.md5(c_code.encode()).hexdigest()[:12]
        cache_file = self.cache_dir / f"{func.name}_{source_hash}.so"

        if sys.platform == "win32":
            cache_file = self.cache_dir / f"{func.name}_{source_hash}.dll"

        # Check cache
        if cache_file.exists():
            return self._load_shared_lib(cache_file, func)

        # Compile
        try:
            self._compile_c(c_code, cache_file)
            return self._load_shared_lib(cache_file, func)
        except Exception as e:
            # Compilation failed, fall back to interpreter
            return None

    def _generate_c(self, func: FunctionDecl) -> str:
        """Generate C code for a Taipan function."""
        # Determine return type
        return_type = self._c_type(func.return_type) if func.return_type else "long long"

        # Build parameter list
        params = []
        for p in func.params:
            ptype = self._c_type(p.type_hint) if p.type_hint else "long long"
            params.append(f"{ptype} {p.name}")

        # Track variable types
        self._var_types: Dict[str, str] = {}
        for p in func.params:
            self._var_types[p.name] = self._c_type(p.type_hint) if p.type_hint else "long long"

        # Generate body
        body_lines = self._generate_block(func.body, indent=1)

        # Build full C code
        c_code = f"""// Auto-generated JIT-compiled Taipan function: {func.name}
#include <stdio.h>
#include <math.h>

{return_type} {func.name}({', '.join(params)}) {{
{chr(10).join(body_lines)}
}}
"""
        return c_code

    def _c_type(self, type_hint: Optional[str]) -> str:
        """Convert Taipan type hint to C type."""
        match type_hint:
            case "Int": return "long long"
            case "Float": return "double"
            case "Bool": return "int"
            case _: return "long long"

    def _generate_block(self, block: Block, indent: int = 0) -> list[str]:
        """Generate C code for a block."""
        lines = []
        for stmt in block.statements:
            lines.extend(self._generate_statement(stmt, indent))
        return lines

    def _generate_statement(self, stmt: Node, indent: int = 0) -> list[str]:
        """Generate C code for a single statement."""
        prefix = "    " * indent

        match stmt:
            case ReturnStmt():
                if stmt.value:
                    return [f"{prefix}return {self._generate_expr(stmt.value)};"]
                return [f"{prefix}return;"]

            case IfStmt():
                cond = self._generate_expr(stmt.condition)
                lines = [f"{prefix}if ({cond}) {{"]
                lines.extend(self._generate_block(stmt.then_branch, indent + 1))
                if stmt.else_branch:
                    lines.append(f"{prefix}}} else {{")
                    if isinstance(stmt.else_branch, Block):
                        lines.extend(self._generate_block(stmt.else_branch, indent + 1))
                    elif isinstance(stmt.else_branch, IfStmt):
                        lines.extend(self._generate_statement(stmt.else_branch, indent + 1))
                lines.append(f"{prefix}}}")
                return lines

            case WhileStmt():
                cond = self._generate_expr(stmt.condition)
                lines = [f"{prefix}while ({cond}) {{"]
                lines.extend(self._generate_block(stmt.body, indent + 1))
                lines.append(f"{prefix}}}")
                return lines

            case ForStmt():
                # For range loops: for (i = start; i < end; i++)
                if isinstance(stmt.iterable, RangeExpr):
                    start = self._generate_expr(stmt.iterable.start)
                    end = self._generate_expr(stmt.iterable.end)
                    step = "1"
                    if stmt.iterable.step:
                        step = self._generate_expr(stmt.iterable.step)
                    var = stmt.variable
                    self._var_types[var] = "long long"
                    if step == "1":
                        lines = [f"{prefix}for (long long {var} = {start}; {var} < {end}; {var}++) {{"]
                    else:
                        lines = [f"{prefix}for (long long {var} = {start}; {var} < {end}; {var} += {step}) {{"]
                    lines.extend(self._generate_block(stmt.body, indent + 1))
                    lines.append(f"{prefix}}}")
                    return lines
                return [f"{prefix}// Unsupported for loop"]

            case VariableDecl():
                var_type = self._c_type(stmt.type_hint)
                if stmt.value:
                    val = self._generate_expr(stmt.value)
                    self._var_types[stmt.name] = var_type
                    return [f"{prefix}{var_type} {stmt.name} = {val};"]
                else:
                    self._var_types[stmt.name] = var_type
                    return [f"{prefix}{var_type} {stmt.name} = 0;"]

            case ConstDecl():
                val = self._generate_expr(stmt.value)
                self._var_types[stmt.name] = self._infer_type(stmt.value)
                return [f"{prefix}const {self._var_types[stmt.name]} {stmt.name} = {val};"]

            case AssignStmt():
                if isinstance(stmt.target, Identifier):
                    val = self._generate_expr(stmt.value)
                    op = stmt.operator
                    if op == "=":
                        return [f"{prefix}{stmt.target.name} = {val};"]
                    elif op == "+=":
                        return [f"{prefix}{stmt.target.name} += {val};"]
                    elif op == "-=":
                        return [f"{prefix}{stmt.target.name} -= {val};"]
                    elif op == "*=":
                        return [f"{prefix}{stmt.target.name} *= {val};"]
                    elif op == "/=":
                        return [f"{prefix}{stmt.target.name} /= {val};"]
                    elif op == "%=":
                        return [f"{prefix}{stmt.target.name} %= {val};"]
                return [f"{prefix}// Unsupported assignment"]

            case ExpressionStmt():
                expr = self._generate_expr(stmt.expression)
                return [f"{prefix}{expr};"]

            case _:
                return [f"{prefix}// Unsupported statement: {type(stmt).__name__}"]

    def _generate_expr(self, expr: Node) -> str:
        """Generate C code for an expression."""
        match expr:
            case IntLiteral():
                return str(expr.value)
            case FloatLiteral():
                return str(expr.value)
            case BoolLiteral():
                return "1" if expr.value else "0"
            case NullLiteral():
                return "0"
            case Identifier():
                return expr.name
            case BinaryExpr():
                left = self._generate_expr(expr.left)
                right = self._generate_expr(expr.right)
                op = self._c_operator(expr.operator)
                return f"({left} {op} {right})"
            case UnaryExpr():
                operand = self._generate_expr(expr.operand)
                match expr.operator:
                    case "-": return f"(-{operand})"
                    case "!" | "not": return f"(!{operand})"
                    case _: return f"({expr.operator}{operand})"
            case RangeExpr():
                return "0"  # Ranges are handled in for loop generation
            case _:
                return "0"

    def _c_operator(self, op: str) -> str:
        """Convert Taipan operator to C operator."""
        mapping = {
            "+": "+", "-": "-", "*": "*", "/": "/", "%": "%", "**": "pow",
            "==": "==", "!=": "!=", "<": "<", "<=": "<=", ">": ">", ">=": ">=",
            "and": "&&", "or": "||",
        }
        return mapping.get(op, op)

    def _infer_type(self, expr: Node) -> str:
        """Infer the C type of an expression."""
        match expr:
            case IntLiteral(): return "long long"
            case FloatLiteral(): return "double"
            case BoolLiteral(): return "int"
            case Identifier():
                return self._var_types.get(expr.name, "long long")
            case BinaryExpr():
                left_type = self._infer_type(expr.left)
                right_type = self._infer_type(expr.right)
                if expr.operator in ("==", "!=", "<", "<=", ">", ">=", "and", "or"):
                    return "int"
                if left_type == "double" or right_type == "double":
                    return "double"
                return "long long"
            case UnaryExpr():
                if expr.operator in ("!", "not"):
                    return "int"
                return self._infer_type(expr.operand)
            case _:
                return "long long"

    def _compile_c(self, c_code: str, output: Path):
        """Compile C code to a shared library."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".c", delete=False) as f:
            f.write(c_code)
            c_file = f.name

        try:
            if sys.platform == "win32":
                # Windows: compile to DLL
                cmd = [self._cc, "-shared", "-O3", "-fPIC", c_file, "-o", str(output), "-lm"]
            elif sys.platform == "darwin":
                # macOS
                cmd = [self._cc, "-shared", "-O3", "-fPIC", c_file, "-o", str(output), "-lm"]
            else:
                # Linux
                cmd = [self._cc, "-shared", "-O3", "-fPIC", c_file, "-o", str(output), "-lm"]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                raise RuntimeError(f"Compilation failed: {result.stderr}")
        finally:
            os.unlink(c_file)

    def _load_shared_lib(self, path: Path, func: FunctionDecl) -> Callable:
        """Load a compiled shared library and return a callable."""
        lib = ctypes.CDLL(str(path))

        # Get the function
        c_func = getattr(lib, func.name)

        # Set argument types based on parameter hints
        argtypes = []
        for p in func.params:
            match p.type_hint:
                case "Int": argtypes.append(ctypes.c_longlong)
                case "Float": argtypes.append(ctypes.c_double)
                case _: argtypes.append(ctypes.c_longlong)

        c_func.argtypes = argtypes

        # Set return type
        match func.return_type:
            case "Int": c_func.restype = ctypes.c_longlong
            case "Float": c_func.restype = ctypes.c_double
            case _: c_func.restype = ctypes.c_longlong

        return c_func


# ── JIT Integration with Interpreter ────────────────────────────────────────────

def jit_compile_function(func: FunctionDecl) -> Optional[Callable]:
    """Convenience function to JIT-compile a single function."""
    compiler = JITCompiler()
    return compiler.compile_function(func)
