"""
Taipan Bytecode VM — Instructions
===================================
Defines opcodes, the Instruction dataclass, and CodeObject.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, List, Optional


class Opcode(Enum):
    # ── Constants & names ────────────────────────────────────────────────────
    LOAD_CONST          = auto()   # push constants[arg]
    LOAD_NAME           = auto()   # push env.get(names[arg])
    DEFINE_NAME         = auto()   # env.define(names[arg], pop())
    DEFINE_CONST        = auto()   # env.define(names[arg], pop(), constant=True)
    STORE_NAME          = auto()   # env.set(names[arg], pop())
    DELETE_NAME         = auto()   # del env[names[arg]] (for temp vars)

    # ── Stack ops ────────────────────────────────────────────────────────────
    POP_TOP             = auto()   # pop and discard
    DUP_TOP             = auto()   # duplicate TOS

    # ── Attributes & indexing ────────────────────────────────────────────────
    LOAD_ATTR           = auto()   # TOS = TOS.names[arg]
    STORE_ATTR          = auto()   # v=pop(); obj=TOS; obj.names[arg]=v
    LOAD_INDEX          = auto()   # idx=pop(); obj=pop(); push obj[idx]
    STORE_INDEX         = auto()   # v=pop(); idx=pop(); obj=TOS; obj[idx]=v

    # ── Operators ────────────────────────────────────────────────────────────
    BINARY_OP           = auto()   # right=pop(); left=pop(); push left op right; arg=names idx
    UNARY_OP            = auto()   # val=pop(); push op(val); arg=names idx

    # ── Jumps ────────────────────────────────────────────────────────────────
    JUMP                = auto()   # ip = arg
    JUMP_IF_FALSE       = auto()   # cond=pop(); if not cond: ip=arg
    JUMP_IF_TRUE        = auto()   # cond=pop(); if cond: ip=arg
    JUMP_IF_FALSE_PEEK  = auto()   # if not TOS (no pop): ip=arg  (short-circuit 'and')
    JUMP_IF_TRUE_PEEK   = auto()   # if TOS (no pop): ip=arg      (short-circuit 'or')

    # ── Iteration ────────────────────────────────────────────────────────────
    GET_ITER            = auto()   # TOS = make_iter(TOS)
    FOR_ITER            = auto()   # TOS=iterator; try next(TOS)→push item(replace iter)
                                   #   or pop+jump on exhaustion; arg=jump target

    # ── Collections ──────────────────────────────────────────────────────────
    BUILD_LIST          = auto()   # pop arg items in order → push PeeList
    BUILD_MAP           = auto()   # pop arg*2 items (key,val pairs) → push PeeMap
    BUILD_TUPLE         = auto()   # pop arg items → push PeeTuple
    BUILD_SET           = auto()   # pop arg items → push PeeSet
    BUILD_RANGE         = auto()   # pop end, start → push PeeRange (arg=0) or also step (arg=1)

    # ── Functions & classes ───────────────────────────────────────────────────
    MAKE_FUNCTION       = auto()   # pop CodeObject, push PeeFunction(names[arg], code, env)
    CALL                = auto()   # pop arg args + callee → push result
    RETURN              = auto()   # return pop() (or None)

    BUILD_CLASS         = auto()   # arg=name idx; pop method_count pairs → build PeeClass
                                   # also pops superclass (or None)

    # ── Exception handling ───────────────────────────────────────────────────
    SETUP_EXCEPT        = auto()   # push handler(catch_ip=arg, var=names[?])
    POP_EXCEPT          = auto()   # pop top handler  (normal exit from try block)
    RAISE               = auto()   # raise pop() as a runtime error

    # ── Misc ─────────────────────────────────────────────────────────────────
    IMPORT              = auto()   # import names[arg]; push result
    SPAWN               = auto()   # spawn pop()
    WAIT                = auto()   # wait all threads
    DEFINE_AI           = auto()   # names[arg] = PeeAI(names[arg]); push it
    NOP                 = auto()   # no-op (used for patching)


@dataclass
class Instruction:
    """A single bytecode instruction."""
    opcode: Opcode
    arg:    Any = None   # int (index), str, None
    # Inline cache fields
    cache_class: Any = None
    cache_is_method: bool = False
    cache_val: Any = None

    def __repr__(self) -> str:
        if self.arg is not None:
            return f"{self.opcode.name}({self.arg!r})"
        return self.opcode.name


@dataclass
class CodeObject:
    """Compiled bytecode for a function, lambda, or module."""
    name:          str           = "<code>"
    instructions:  List[Instruction] = field(default_factory=list)
    constants:     List[Any]     = field(default_factory=list)   # literals + nested CodeObjects
    names:         List[str]     = field(default_factory=list)   # variables / attribute names
    params:        List[str]     = field(default_factory=list)   # parameter names
    defaults:      List[Any]     = field(default_factory=list)   # pre-evaluated default values (or _MISSING)

    def disassemble(self) -> str:
        """Return a human-readable disassembly."""
        lines = [f"<CodeObject '{self.name}'>"]
        for i, instr in enumerate(self.instructions):
            extra = ""
            if instr.opcode in (Opcode.LOAD_CONST,) and instr.arg is not None:
                c = self.constants[instr.arg]
                extra = f"  ; {c!r}" if not isinstance(c, CodeObject) else f"  ; <code '{c.name}'>"
            elif instr.opcode in (Opcode.LOAD_NAME, Opcode.DEFINE_NAME, Opcode.DEFINE_CONST,
                                  Opcode.STORE_NAME, Opcode.LOAD_ATTR, Opcode.STORE_ATTR,
                                  Opcode.BINARY_OP, Opcode.UNARY_OP, Opcode.MAKE_FUNCTION,
                                  Opcode.IMPORT, Opcode.DEFINE_AI, Opcode.BUILD_CLASS):
                if instr.arg is not None and instr.arg < len(self.names):
                    extra = f"  ; '{self.names[instr.arg]}'"
            lines.append(f"  {i:4d}  {instr!r}{extra}")
        return "\n".join(lines)


# Sentinel for missing defaults
_MISSING = object()
