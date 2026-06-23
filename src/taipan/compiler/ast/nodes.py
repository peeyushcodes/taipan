"""
Taipan AST Nodes
=================
All Abstract Syntax Tree node types used by the Taipan parser and interpreter.
Every node is a dataclass for clean field access and printing.

Design note: To avoid Python dataclass inheritance issues with default/non-default
field ordering, we use `field(default=0)` on the base class and `kw_only=True`
on subclasses (Python 3.10+), allowing any field order.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, List, Optional


# ── Base ──────────────────────────────────────────────────────────────────────

@dataclass
class Node:
    """Base class for all AST nodes. Stores source location."""
    line:   int = field(default=0, repr=False)
    column: int = field(default=0, repr=False)


# ── Helper to create AST node classes ────────────────────────────────────────
# We use kw_only=True (Python 3.10+) so subclass fields with no defaults can
# follow base-class fields that have defaults.

def _node(*args, **kwargs):
    """Decorator that creates a kw_only dataclass inheriting from Node."""
    def wrap(cls):
        return dataclass(cls, kw_only=True)
    return wrap


# ── Top-level ─────────────────────────────────────────────────────────────────

@dataclass(kw_only=True)
class Program(Node):
    """Root node — list of top-level statements."""
    body: List[Node] = field(default_factory=list)


@dataclass(kw_only=True)
class Block(Node):
    """A { … } block of statements."""
    statements: List[Node] = field(default_factory=list)


# ── Statements ────────────────────────────────────────────────────────────────

@dataclass(kw_only=True)
class VariableDecl(Node):
    """let name [: type_hint] = value"""
    name:      str
    value:     Optional[Node]
    type_hint: Optional[str] = None
    mutable:   bool = True


@dataclass(kw_only=True)
class ConstDecl(Node):
    """const NAME = value"""
    name:  str
    value: Node


@dataclass(kw_only=True)
class AssignStmt(Node):
    """name = expr  or  name op= expr  (augmented assignment)"""
    target:   Node        # Identifier or MemberExpr or IndexExpr
    value:    Node
    operator: str = "="   # "=", "+=", "-=", "*=", "/="


@dataclass(kw_only=True)
class FunctionDecl(Node):
    """func name(params) [-> return_type] { body }"""
    name:        str
    params:      List["Param"]
    body:        Block
    return_type: Optional[str] = None
    is_method:   bool = False


@dataclass(kw_only=True)
class Param(Node):
    """A single function parameter: name [: type_hint]"""
    name:      str
    type_hint: Optional[str] = None
    default:   Optional[Node] = None


@dataclass(kw_only=True)
class ClassDecl(Node):
    """class Name [extends Base] { body }"""
    name:       str
    body:       Block
    superclass: Optional[str] = None


@dataclass(kw_only=True)
class ReturnStmt(Node):
    """return [expr]"""
    value: Optional[Node] = None


@dataclass(kw_only=True)
class IfStmt(Node):
    """if condition { then } [else { else_branch }]"""
    condition:   Node
    then_branch: Block
    else_branch: Optional[Node] = None   # Block or another IfStmt


@dataclass(kw_only=True)
class WhileStmt(Node):
    """while condition { body }"""
    condition: Node
    body:      Block


@dataclass(kw_only=True)
class ForStmt(Node):
    """for var in iterable { body }"""
    variable: str
    iterable: Node
    body:     Block


@dataclass(kw_only=True)
class RepeatStmt(Node):
    """repeat n { body }"""
    count: Node
    body:  Block


@dataclass(kw_only=True)
class TryCatchStmt(Node):
    """try { … } catch err { … }"""
    try_block:   Block
    error_var:   str
    catch_block: Block


@dataclass(kw_only=True)
class ImportStmt(Node):
    """import module_name | import python \"module_name\""""
    module:  str
    alias:   Optional[str] = None
    backend: str = "taipan"  # "taipan" or "python"



@dataclass(kw_only=True)
class SpawnStmt(Node):
    """spawn expression (usually a function call)"""
    expression: Node


@dataclass(kw_only=True)
class WaitStmt(Node):
    """wait — join all spawned threads"""
    pass


@dataclass(kw_only=True)
class AiDeclStmt(Node):
    """ai identifier — creates an AI assistant instance"""
    name: str


@dataclass(kw_only=True)
class TestStmt(Node):
    """test "name" { body } — unit test declaration"""
    name: str
    body: Block


@dataclass(kw_only=True)
class BreakStmt(Node):
    """break"""
    pass


@dataclass(kw_only=True)
class ContinueStmt(Node):
    """continue"""
    pass


@dataclass(kw_only=True)
class ExpressionStmt(Node):
    """A bare expression used as a statement."""
    expression: Node


# ── Expressions ───────────────────────────────────────────────────────────────

@dataclass(kw_only=True)
class BinaryExpr(Node):
    """left op right"""
    left:     Node
    operator: str
    right:    Node


@dataclass(kw_only=True)
class UnaryExpr(Node):
    """op operand"""
    operator: str
    operand:  Node


@dataclass(kw_only=True)
class CallExpr(Node):
    """callee(args)"""
    callee:    Node
    arguments: List[Node] = field(default_factory=list)


@dataclass(kw_only=True)
class MemberExpr(Node):
    """object.property"""
    object:   Node
    property: str


@dataclass(kw_only=True)
class IndexExpr(Node):
    """object[index]"""
    object: Node
    index:  Node


@dataclass(kw_only=True)
class RangeExpr(Node):
    """start..end [..step]"""
    start:     Node
    end:       Node
    step:      Optional[Node] = None
    inclusive: bool = False


@dataclass(kw_only=True)
class LambdaExpr(Node):
    """func(params) => expr  (single-expression lambda)"""
    params: List[Param]
    body:   Node


# ── Literals ──────────────────────────────────────────────────────────────────

@dataclass(kw_only=True)
class IntLiteral(Node):
    value: int


@dataclass(kw_only=True)
class FloatLiteral(Node):
    value: float


@dataclass(kw_only=True)
class StringLiteral(Node):
    value: str


@dataclass(kw_only=True)
class FStringLiteral(Node):
    """f\"Hello {name}!\"  — interpolated string.
    parts is a list of ('lit', str) or ('expr', Node).
    """
    parts: list = field(default_factory=list)


@dataclass(kw_only=True)
class BoolLiteral(Node):
    value: bool


@dataclass(kw_only=True)
class NullLiteral(Node):
    pass


@dataclass(kw_only=True)
class Identifier(Node):
    name: str


@dataclass(kw_only=True)
class ListLiteral(Node):
    elements: List[Node] = field(default_factory=list)


@dataclass(kw_only=True)
class MapLiteral(Node):
    """{ key: value, … }"""
    pairs: List[tuple] = field(default_factory=list)   # list of (key_node, val_node)


@dataclass(kw_only=True)
class SetLiteral(Node):
    """set literal — written as set([…]) in source or {| … |}"""
    elements: List[Node] = field(default_factory=list)


@dataclass(kw_only=True)
class TupleLiteral(Node):
    """(a, b, c)"""
    elements: List[Node] = field(default_factory=list)


# ── Match / Switch ────────────────────────────────────────────────────────────

@dataclass(kw_only=True)
class MatchCase(Node):
    """case pattern: { body }"""
    pattern: Node
    body:    Block


@dataclass(kw_only=True)
class MatchStmt(Node):
    """match expr { case p1: { … } case p2: { … } default: { … } }"""
    subject: Node
    cases:   List[MatchCase] = field(default_factory=list)
    default: Optional[Block] = None
