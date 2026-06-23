"""
Taipan Runtime Environment
============================
Implements lexical scoping via a chain of Environment objects.

Each Environment holds a dict of name → value and an optional parent.
Variable lookup walks up the chain; assignment mutates the nearest defining scope.
"""

from __future__ import annotations
from typing import Any, Optional
from taipan.runtime.errors import TaipanNameError


class Environment:
    """
    A single scope (function call frame, block, or global scope).
    Parent scoping implements lexical variable lookup.
    """

    def __init__(self, parent: Optional[Environment] = None, name: str = "<scope>"):
        self._vars:  dict[str, Any] = {}
        self._consts: set[str] = set()
        self.parent = parent
        self.name   = name

    # ── Core API ──────────────────────────────────────────────────────────────

    def define(self, name: str, value: Any, constant: bool = False):
        """Declare a new variable in *this* scope."""
        self._vars[name] = value
        if constant:
            self._consts.add(name)

    def get(self, name: str, line: int = 0, col: int = 0) -> Any:
        """Look up a variable, walking up to parent scopes."""
        if name in self._vars:
            return self._vars[name]
        if self.parent is not None:
            return self.parent.get(name, line, col)
        raise TaipanNameError(f"'{name}' is not defined", line, col)

    def set(self, name: str, value: Any, line: int = 0, col: int = 0):
        """Assign to an *existing* variable in the nearest defining scope."""
        if name in self._vars:
            if name in self._consts:
                raise TaipanNameError(
                    f"Cannot reassign constant '{name}'", line, col
                )
            self._vars[name] = value
            return
        if self.parent is not None:
            self.parent.set(name, value, line, col)
            return
        raise TaipanNameError(f"'{name}' is not defined", line, col)

    def assign_or_define(self, name: str, value: Any):
        """
        Assign if the variable exists anywhere in the chain,
        otherwise define it in the global scope.
        Used for bare assignments without 'let'.
        """
        try:
            self.set(name, value)
        except TaipanNameError:
            self.define(name, value)

    def has(self, name: str) -> bool:
        """Check whether a name exists in any reachable scope."""
        if name in self._vars:
            return True
        if self.parent is not None:
            return self.parent.has(name)
        return False

    # ── Scope management ──────────────────────────────────────────────────────

    def child(self, name: str = "<child>") -> "Environment":
        """Create a child scope that inherits from this one."""
        return Environment(parent=self, name=name)

    def global_scope(self) -> "Environment":
        """Walk up to the root scope."""
        env = self
        while env.parent is not None:
            env = env.parent
        return env

    # ── Debug ─────────────────────────────────────────────────────────────────

    def dump(self, indent: int = 0) -> str:
        lines = [" " * indent + f"[{self.name}]"]
        for k, v in self._vars.items():
            lines.append(" " * (indent + 2) + f"{k} = {v!r}")
        if self.parent:
            lines.append(self.parent.dump(indent + 2))
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"Environment({self.name!r}, vars={list(self._vars.keys())})"
