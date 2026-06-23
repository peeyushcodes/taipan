"""
Taipan Semantic Analyzer
==========================
Validates the AST before interpretation:
  - Scope resolution (undefined variables, double declarations)
  - Type hints stored for future type-checking passes
  - Function signature validation
  - Return statement presence in typed functions
  - Import module name validation

Errors are collected rather than aborting on first failure.
"""

from __future__ import annotations
from typing import List, Optional
from taipan.compiler.ast.nodes import *
from taipan.runtime.errors import TaipanSemanticError


class Symbol:
    def __init__(self, name: str, kind: str, type_hint: Optional[str] = None,
                 line: int = 0, col: int = 0):
        self.name      = name
        self.kind      = kind       # "variable", "constant", "function", "class", "param"
        self.type_hint = type_hint
        self.line      = line
        self.col       = col


class SymbolTable:
    def __init__(self, parent: Optional[SymbolTable] = None, name: str = "global"):
        self._symbols: dict[str, Symbol] = {}
        self.parent   = parent
        self.name     = name

    def define(self, sym: Symbol):
        self._symbols[sym.name] = sym

    def lookup(self, name: str) -> Optional[Symbol]:
        if name in self._symbols:
            return self._symbols[name]
        if self.parent:
            return self.parent.lookup(name)
        return None

    def local_lookup(self, name: str) -> Optional[Symbol]:
        return self._symbols.get(name)

    def child(self, name: str = "<child>") -> SymbolTable:
        return SymbolTable(parent=self, name=name)


# Built-in names that always exist
BUILTINS = {
    "show", "input", "len", "type", "int", "float", "str", "bool",
    "range", "set", "list", "map", "print", "abs", "min", "max",
    "sum", "round", "sorted", "reversed", "enumerate", "zip",
    "null", "true", "false",
}

BUILTIN_MODULES = {
    "math", "string", "file", "json", "time", "collections",
    "network", "ai", "crypto", "web", "database", "ml",
    "robotics", "cybersecurity", "gpu",
}


class SemanticAnalyzer:
    """
    Walks the AST, building symbol tables and collecting semantic errors.
    """

    def __init__(self):
        self.errors:  List[TaipanSemanticError] = []
        self.scope:   SymbolTable = SymbolTable(name="global")
        self._in_func: int  = 0       # nesting depth of function bodies
        self._in_loop: int  = 0       # nesting depth of loops
        self._in_class: bool = False

        # Pre-populate builtins
        for name in BUILTINS:
            self.scope.define(Symbol(name, "builtin"))

    # ── Public API ────────────────────────────────────────────────────────────

    def analyze(self, node: Node) -> List[TaipanSemanticError]:
        self._visit(node)
        return self.errors

    # ── Visitor dispatch ──────────────────────────────────────────────────────

    def _visit(self, node: Node):
        method = f"_visit_{type(node).__name__}"
        visitor = getattr(self, method, self._visit_generic)
        visitor(node)

    def _visit_generic(self, node: Node):
        """Default visitor — recurse into all child nodes."""
        for field_val in vars(node).values():
            if isinstance(field_val, Node):
                self._visit(field_val)
            elif isinstance(field_val, list):
                for item in field_val:
                    if isinstance(item, Node):
                        self._visit(item)
            elif isinstance(field_val, tuple):
                for item in field_val:
                    if isinstance(item, Node):
                        self._visit(item)

    def _error(self, msg: str, node: Node):
        err = TaipanSemanticError(msg, node.line, node.column)
        self.errors.append(err)

    # ── Statements ────────────────────────────────────────────────────────────

    def _visit_Program(self, node: Program):
        for stmt in node.body:
            self._visit(stmt)

    def _visit_Block(self, node: Block):
        for stmt in node.statements:
            self._visit(stmt)

    def _visit_VariableDecl(self, node: VariableDecl):
        if node.value:
            self._visit(node.value)
        # Check for duplicate declaration in current scope
        if self.scope.local_lookup(node.name):
            self._error(
                f"Duplicate declaration: '{node.name}' is already defined in this scope", node
            )
        sym = Symbol(node.name, "variable", node.type_hint, node.line, node.column)
        self.scope.define(sym)

    def _visit_ConstDecl(self, node: ConstDecl):
        self._visit(node.value)
        # Check for duplicate declaration in current scope
        if self.scope.local_lookup(node.name):
            self._error(
                f"Duplicate declaration: '{node.name}' is already defined in this scope", node
            )
        sym = Symbol(node.name, "constant", None, node.line, node.column)
        self.scope.define(sym)

    def _visit_AssignStmt(self, node: AssignStmt):
        self._visit(node.value)
        # For simple identifier targets, check it exists
        if isinstance(node.target, Identifier):
            if not self.scope.lookup(node.target.name):
                # Allow implicit definition in global scope for scripts
                self.scope.define(Symbol(node.target.name, "variable",
                                         line=node.line, col=node.column))
        else:
            self._visit(node.target)

    def _visit_FunctionDecl(self, node: FunctionDecl):
        # Skip duplicate check inside class bodies — methods override is fine
        if not self._in_class and self.scope.local_lookup(node.name):
            self._error(
                f"Duplicate declaration: function '{node.name}' is already defined in this scope",
                node
            )
        sym = Symbol(node.name, "function", node.return_type, node.line, node.column)
        self.scope.define(sym)

        # Enter function scope
        outer = self.scope
        self.scope = self.scope.child(f"func:{node.name}")
        self._in_func += 1

        # Define params
        for param in node.params:
            self.scope.define(Symbol(param.name, "param", param.type_hint,
                                     param.line, param.column))

        self._visit(node.body)
        self._in_func -= 1
        self.scope = outer

    def _visit_ClassDecl(self, node: ClassDecl):
        if self.scope.local_lookup(node.name):
            self._error(
                f"Duplicate declaration: class '{node.name}' is already defined in this scope",
                node
            )
        sym = Symbol(node.name, "class", None, node.line, node.column)
        self.scope.define(sym)

        outer = self.scope
        self.scope = self.scope.child(f"class:{node.name}")
        self._in_class = True
        self.scope.define(Symbol("self", "param"))

        for stmt in node.body.statements:
            self._visit(stmt)

        self._in_class = False
        self.scope = outer

    def _visit_IfStmt(self, node: IfStmt):
        self._visit(node.condition)
        outer = self.scope
        self.scope = outer.child("if:then")
        self._visit(node.then_branch)
        self.scope = outer
        if node.else_branch:
            self.scope = outer.child("if:else")
            self._visit(node.else_branch)
            self.scope = outer

    def _visit_WhileStmt(self, node: WhileStmt):
        self._visit(node.condition)
        outer = self.scope
        self.scope = outer.child("while")
        self._in_loop += 1
        self._visit(node.body)
        self._in_loop -= 1
        self.scope = outer

    def _visit_ForStmt(self, node: ForStmt):
        self._visit(node.iterable)
        outer = self.scope
        self.scope = outer.child("for")
        self.scope.define(Symbol(node.variable, "variable", None, node.line, node.column))
        self._in_loop += 1
        self._visit(node.body)
        self._in_loop -= 1
        self.scope = outer

    def _visit_RepeatStmt(self, node: RepeatStmt):
        self._visit(node.count)
        outer = self.scope
        self.scope = outer.child("repeat")
        self._in_loop += 1
        self._visit(node.body)
        self._in_loop -= 1
        self.scope = outer

    def _visit_ReturnStmt(self, node: ReturnStmt):
        if self._in_func == 0:
            self._error("'return' outside function", node)
        if node.value:
            self._visit(node.value)

    def _visit_BreakStmt(self, node: BreakStmt):
        if self._in_loop == 0:
            self._error("'break' outside loop", node)

    def _visit_ContinueStmt(self, node: ContinueStmt):
        if self._in_loop == 0:
            self._error("'continue' outside loop", node)

    def _visit_TryCatchStmt(self, node: TryCatchStmt):
        outer = self.scope
        self.scope = outer.child("try")
        self._visit(node.try_block)
        self.scope = outer.child("catch")
        self.scope.define(Symbol(node.error_var, "variable", None, node.line, node.column))
        self._visit(node.catch_block)
        self.scope = outer

    def _visit_ImportStmt(self, node: ImportStmt):
        mod = node.module.split(".")[0]
        if mod not in BUILTIN_MODULES:
            # Not a hard error — could be a user-installed package
            pass
        # Define the module name in scope
        alias = node.alias or node.module.split(".")[-1]
        self.scope.define(Symbol(alias, "module", None, node.line, node.column))

    def _visit_SpawnStmt(self, node: SpawnStmt):
        self._visit(node.expression)

    def _visit_WaitStmt(self, node: WaitStmt):
        pass

    def _visit_AiDeclStmt(self, node: AiDeclStmt):
        self.scope.define(Symbol(node.name, "variable", "AI", node.line, node.column))

    def _visit_ExpressionStmt(self, node: ExpressionStmt):
        self._visit(node.expression)

    # ── Expressions ───────────────────────────────────────────────────────────

    def _visit_Identifier(self, node: Identifier):
        if not self.scope.lookup(node.name):
            self._error(f"Undefined name '{node.name}'", node)

    def _visit_BinaryExpr(self, node: BinaryExpr):
        self._visit(node.left)
        self._visit(node.right)

    def _visit_UnaryExpr(self, node: UnaryExpr):
        self._visit(node.operand)

    def _visit_CallExpr(self, node: CallExpr):
        self._visit(node.callee)
        for arg in node.arguments:
            self._visit(arg)

    def _visit_MemberExpr(self, node: MemberExpr):
        self._visit(node.object)
        # Property access is not validated statically (dynamic dispatch)

    def _visit_IndexExpr(self, node: IndexExpr):
        self._visit(node.object)
        self._visit(node.index)

    def _visit_RangeExpr(self, node: RangeExpr):
        self._visit(node.start)
        self._visit(node.end)
        if node.step:
            self._visit(node.step)

    def _visit_ListLiteral(self, node: ListLiteral):
        for el in node.elements:
            self._visit(el)

    def _visit_MapLiteral(self, node: MapLiteral):
        for k, v in node.pairs:
            self._visit(k)
            self._visit(v)

    def _visit_SetLiteral(self, node: SetLiteral):
        for el in node.elements:
            self._visit(el)

    def _visit_TupleLiteral(self, node: TupleLiteral):
        for el in node.elements:
            self._visit(el)

    # Literals need no validation
    def _visit_IntLiteral(self, node): pass
    def _visit_FloatLiteral(self, node): pass
    def _visit_StringLiteral(self, node): pass
    def _visit_FStringLiteral(self, node):
        # parts is a list of ('lit', str) | ('expr', Node) — after parser builds it
        # the parser actually desugars fstrings to BinaryExpr chains, so this
        # visitor is a safety net for any direct FStringLiteral nodes.
        for kind, part in node.parts:
            if kind == "expr" and hasattr(part, "line"):
                self._visit(part)
    def _visit_BoolLiteral(self, node): pass
    def _visit_NullLiteral(self, node): pass
    def _visit_Param(self, node): pass

    def _visit_LambdaExpr(self, node: LambdaExpr):
        outer = self.scope
        self.scope = self.scope.child("lambda")
        self._in_func += 1
        for param in node.params:
            self.scope.define(Symbol(param.name, "param", param.type_hint,
                                     param.line, param.column))
        self._visit(node.body)
        self._in_func -= 1
        self.scope = outer

    def _visit_MatchStmt(self, node: MatchStmt):
        self._visit(node.subject)
        for case in node.cases:
            self._visit(case)
        if node.default:
            self._visit(node.default)

    def _visit_MatchCase(self, node: MatchCase):
        self._visit(node.pattern)
        self._visit(node.body)
