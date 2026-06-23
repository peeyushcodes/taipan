"""
Taipan Bytecode Compiler
==========================
Compiles a Taipan AST into a CodeObject (bytecode).

Handles all Taipan language features:
  - Variables, constants, assignments
  - Functions (with closures and defaults), lambdas
  - Classes and inheritance
  - Control flow: if/else, while, for, repeat, break, continue
  - Try/catch, match/case
  - Spawn/wait concurrency
  - Import (stdlib + user modules)
  - All expression types and operators
  - F-strings (already desugared to BinaryExpr chains by the parser)
"""

from __future__ import annotations
from typing import Any, List, Optional

from taipan.compiler.ast.nodes import *
from taipan.compiler.vm.instructions import Opcode, Instruction, CodeObject, _MISSING


class _LoopCtx:
    """Tracks break/continue targets for loop compilation."""
    def __init__(self, continue_ip: int):
        self.continue_ip  = continue_ip
        self.break_patches: List[int] = []   # instruction indices to patch


class _ExceptCtx:
    """Tracks setup/teardown info for try blocks."""
    def __init__(self, catch_ip_patch: int, var_idx: int):
        self.catch_ip_patch = catch_ip_patch   # instruction index of SETUP_EXCEPT to patch
        self.var_idx        = var_idx           # names index of error variable


class BytecodeCompiler:
    """
    Compiles a Taipan AST (Program or Block) into a CodeObject.

    Usage:
        co = BytecodeCompiler().compile(ast_program)
    """

    def __init__(self, name: str = "<module>", params: List[str] = None):
        self._code   = CodeObject(name=name, params=params or [])
        self._loops:  List[_LoopCtx] = []    # stack of active loop contexts
        self._iter_id = 0                     # counter for hidden iterator locals

    # ── Public API ────────────────────────────────────────────────────────────

    def compile(self, node: Node) -> CodeObject:
        """Compile a Program or Block node into this compiler's CodeObject."""
        self._compile_node(node)
        self._optimize()
        return self._code

    # ── Emit helpers ──────────────────────────────────────────────────────────

    def _emit(self, opcode: Opcode, arg: Any = None) -> int:
        """Append an instruction and return its index."""
        self._code.instructions.append(Instruction(opcode, arg))
        return len(self._code.instructions) - 1

    def _here(self) -> int:
        """Return the index of the NEXT instruction to be emitted."""
        return len(self._code.instructions)

    def _patch(self, ip: int, target: int):
        """Patch a jump instruction's target."""
        self._code.instructions[ip].arg = target

    def _const(self, val: Any) -> int:
        """Add a constant to the constants pool and return its index.

        Uses strict type-aware deduplication to prevent Python's bool/int
        aliasing (``False == 0`` and ``True == 1``) from corrupting the pool.
        """
        for idx, v in enumerate(self._code.constants):
            if type(v) is type(val) and v == val:
                return idx
        self._code.constants.append(val)
        return len(self._code.constants) - 1


    def _name(self, name: str) -> int:
        """Add a name to the names pool and return its index."""
        if name not in self._code.names:
            self._code.names.append(name)
        return self._code.names.index(name)

    def _next_iter_name(self) -> str:
        n = f"__pee_iter_{self._iter_id}"
        self._iter_id += 1
        return n

    # ── Node dispatch ─────────────────────────────────────────────────────────

    def _compile_node(self, node: Node):
        method = f"_compile_{type(node).__name__}"
        fn = getattr(self, method, None)
        if fn is None:
            raise NotImplementedError(
                f"BytecodeCompiler: no handler for {type(node).__name__}"
            )
        fn(node)

    # ── Top-level ─────────────────────────────────────────────────────────────

    def _compile_Program(self, node: Program):
        for stmt in node.body:
            self._compile_node(stmt)

    def _compile_Block(self, node: Block):
        for stmt in node.statements:
            self._compile_node(stmt)

    # ── Statements ────────────────────────────────────────────────────────────

    def _compile_ExpressionStmt(self, node: ExpressionStmt):
        self._compile_node(node.expression)
        self._emit(Opcode.POP_TOP)

    def _compile_VariableDecl(self, node: VariableDecl):
        if node.value is not None:
            self._compile_node(node.value)
        else:
            self._emit(Opcode.LOAD_CONST, self._const(None))
        self._emit(Opcode.DEFINE_NAME, self._name(node.name))

    def _compile_ConstDecl(self, node: ConstDecl):
        self._compile_node(node.value)
        self._emit(Opcode.DEFINE_CONST, self._name(node.name))

    def _compile_AssignStmt(self, node: AssignStmt):
        if node.operator != "=":
            # Augmented: load current value, apply op, store
            self._compile_node(node.target)
            self._compile_node(node.value)
            op = node.operator[:-1]   # "+=" → "+"
            self._emit(Opcode.BINARY_OP, self._name(op))
        else:
            self._compile_node(node.value)

        # Assign to target
        if isinstance(node.target, Identifier):
            self._emit(Opcode.STORE_NAME, self._name(node.target.name))
        elif isinstance(node.target, MemberExpr):
            self._compile_node(node.target.object)
            self._emit(Opcode.STORE_ATTR, self._name(node.target.property))
        elif isinstance(node.target, IndexExpr):
            self._compile_node(node.target.object)
            self._compile_node(node.target.index)
            self._emit(Opcode.STORE_INDEX)
        else:
            raise NotImplementedError(f"Cannot assign to {type(node.target).__name__}")

    def _compile_FunctionDecl(self, node: FunctionDecl):
        # Compile the body in a sub-compiler
        sub = BytecodeCompiler(name=node.name, params=[p.name for p in node.params])
        # Pre-evaluate defaults (compile-time simplification: literals only for VM)
        defaults = []
        for param in node.params:
            if param.default is not None:
                # Compile default to its own code object
                d_sub = BytecodeCompiler(name=f"<default:{param.name}>")
                d_sub._compile_node(param.default)
                d_sub._emit(Opcode.RETURN)
                d_sub._optimize()
                defaults.append(d_sub._code)
            else:
                defaults.append(_MISSING)
        sub._code.defaults = defaults
        sub._compile_node(node.body)
        sub._emit(Opcode.LOAD_CONST, sub._const(None))
        sub._emit(Opcode.RETURN)
        sub._optimize()

        # Store sub-code as constant, emit MAKE_FUNCTION + DEFINE_NAME
        co_idx = self._const(sub._code)
        self._emit(Opcode.LOAD_CONST, co_idx)
        self._emit(Opcode.MAKE_FUNCTION, self._name(node.name))
        self._emit(Opcode.DEFINE_NAME, self._name(node.name))

    def _compile_LambdaExpr(self, node: LambdaExpr):
        sub = BytecodeCompiler(name="<lambda>", params=[p.name for p in node.params])
        sub._code.defaults = [_MISSING] * len(node.params)
        # Lambda body is an expression; compile it and RETURN its value
        sub._compile_node(node.body)
        sub._emit(Opcode.RETURN)
        sub._optimize()

        co_idx = self._const(sub._code)
        self._emit(Opcode.LOAD_CONST, co_idx)
        self._emit(Opcode.MAKE_FUNCTION, self._name("<lambda>"))

    def _compile_ClassDecl(self, node: ClassDecl):
        # Push superclass (or None)
        if node.superclass:
            self._emit(Opcode.LOAD_NAME, self._name(node.superclass))
        else:
            self._emit(Opcode.LOAD_CONST, self._const(None))

        # Compile each method and push (name_const, function) pairs
        method_count = 0
        for stmt in node.body.statements:
            if isinstance(stmt, FunctionDecl):
                # Push method name
                self._emit(Opcode.LOAD_CONST, self._const(stmt.name))
                # Compile method body
                sub = BytecodeCompiler(name=stmt.name, params=[p.name for p in stmt.params])
                sub._code.defaults = [
                    (_MISSING if p.default is None else p.default)
                    for p in stmt.params
                ]
                sub._compile_node(stmt.body)
                sub._emit(Opcode.LOAD_CONST, sub._const(None))
                sub._emit(Opcode.RETURN)
                co_idx = self._const(sub._code)
                self._emit(Opcode.LOAD_CONST, co_idx)
                self._emit(Opcode.MAKE_FUNCTION, self._name(stmt.name))
                method_count += 1

        # BUILD_CLASS pops: superclass, then method_count*(name, fn) pairs
        self._emit(Opcode.LOAD_CONST, self._const(method_count))
        self._emit(Opcode.BUILD_CLASS, self._name(node.name))
        self._emit(Opcode.DEFINE_NAME, self._name(node.name))


    def _compile_IfStmt(self, node: IfStmt):
        self._compile_node(node.condition)
        else_jump = self._emit(Opcode.JUMP_IF_FALSE, None)    # patch later

        self._compile_node(node.then_branch)

        if node.else_branch is not None:
            end_jump = self._emit(Opcode.JUMP, None)          # skip else
            self._patch(else_jump, self._here())
            self._compile_node(node.else_branch)
            self._patch(end_jump, self._here())
        else:
            self._patch(else_jump, self._here())

    def _compile_WhileStmt(self, node: WhileStmt):
        loop_top = self._here()
        ctx = _LoopCtx(continue_ip=loop_top)
        self._loops.append(ctx)

        self._compile_node(node.condition)
        exit_jump = self._emit(Opcode.JUMP_IF_FALSE, None)

        self._compile_node(node.body)
        self._emit(Opcode.JUMP, loop_top)

        loop_end = self._here()
        self._patch(exit_jump, loop_end)
        for bp in ctx.break_patches:
            self._patch(bp, loop_end)
        self._loops.pop()

    def _compile_ForStmt(self, node: ForStmt):
        # Compile iterable, get iterator, store in hidden local
        self._compile_node(node.iterable)
        self._emit(Opcode.GET_ITER)
        iter_name = self._next_iter_name()
        self._emit(Opcode.DEFINE_NAME, self._name(iter_name))

        loop_top = self._here()
        ctx = _LoopCtx(continue_ip=loop_top)
        self._loops.append(ctx)

        # Load iterator, try next → push item (replace TOS) or jump past loop
        self._emit(Opcode.LOAD_NAME, self._name(iter_name))
        for_iter_ip = self._emit(Opcode.FOR_ITER, None)        # patched later
        self._emit(Opcode.STORE_NAME, self._name(node.variable))

        self._compile_node(node.body)
        self._emit(Opcode.JUMP, loop_top)

        loop_end = self._here()
        self._patch(for_iter_ip, loop_end)
        for bp in ctx.break_patches:
            self._patch(bp, loop_end)
        self._loops.pop()

        # Clean up hidden iterator
        self._emit(Opcode.LOAD_CONST, self._const(None))
        self._emit(Opcode.STORE_NAME, self._name(iter_name))

    def _compile_RepeatStmt(self, node: RepeatStmt):
        # repeat N { body } → for __i in range(0, N) { body }
        self._emit(Opcode.LOAD_CONST, self._const(0))
        self._compile_node(node.count)
        self._emit(Opcode.BUILD_RANGE, 0)
        self._emit(Opcode.GET_ITER)
        iter_name = self._next_iter_name()
        self._emit(Opcode.DEFINE_NAME, self._name(iter_name))

        loop_top = self._here()
        ctx = _LoopCtx(continue_ip=loop_top)
        self._loops.append(ctx)

        self._emit(Opcode.LOAD_NAME, self._name(iter_name))
        for_iter_ip = self._emit(Opcode.FOR_ITER, None)
        self._emit(Opcode.POP_TOP)   # discard loop variable

        self._compile_node(node.body)
        self._emit(Opcode.JUMP, loop_top)

        loop_end = self._here()
        self._patch(for_iter_ip, loop_end)
        for bp in ctx.break_patches:
            self._patch(bp, loop_end)
        self._loops.pop()

    def _compile_ReturnStmt(self, node: ReturnStmt):
        if node.value is not None:
            self._compile_node(node.value)
        else:
            self._emit(Opcode.LOAD_CONST, self._const(None))
        self._emit(Opcode.RETURN)

    def _compile_BreakStmt(self, node: BreakStmt):
        if not self._loops:
            return  # semantic error already caught
        bp = self._emit(Opcode.JUMP, None)
        self._loops[-1].break_patches.append(bp)

    def _compile_ContinueStmt(self, node: ContinueStmt):
        if not self._loops:
            return
        self._emit(Opcode.JUMP, self._loops[-1].continue_ip)

    def _compile_TryCatchStmt(self, node: TryCatchStmt):
        self._emit(Opcode.LOAD_CONST, self._const(node.error_var))  # var name for handler
        setup_ip = self._emit(Opcode.SETUP_EXCEPT, None)         # patched after try


        self._compile_node(node.try_block)
        self._emit(Opcode.POP_EXCEPT)
        end_jump = self._emit(Opcode.JUMP, None)                  # skip catch

        catch_ip = self._here()
        self._patch(setup_ip, catch_ip)

        # In catch: TOS is the error message (pushed by VM handler)
        self._emit(Opcode.DEFINE_NAME, self._name(node.error_var))
        self._compile_node(node.catch_block)

        self._patch(end_jump, self._here())

    def _compile_ImportStmt(self, node: ImportStmt):
        alias = node.alias or node.module.split(".")[-1]
        self._emit(Opcode.IMPORT, self._name(node.module))
        self._emit(Opcode.DEFINE_NAME, self._name(alias))

    def _compile_SpawnStmt(self, node: SpawnStmt):
        sub = BytecodeCompiler(name="<spawn>")
        sub._compile_node(node.expression)
        sub._emit(Opcode.POP_TOP)  # discard result of expression
        sub._emit(Opcode.LOAD_CONST, sub._const(None))
        sub._emit(Opcode.RETURN)

        co_idx = self._const(sub._code)
        self._emit(Opcode.LOAD_CONST, co_idx)
        self._emit(Opcode.MAKE_FUNCTION, self._name("<spawn>"))
        self._emit(Opcode.SPAWN)


    def _compile_WaitStmt(self, node: WaitStmt):
        self._emit(Opcode.WAIT)

    def _compile_AiDeclStmt(self, node: AiDeclStmt):
        self._emit(Opcode.DEFINE_AI, self._name(node.name))

    def _compile_MatchStmt(self, node: MatchStmt):
        # Evaluate subject once, store in hidden var
        subject_name = f"__pee_match_{self._next_iter_name()}"
        self._compile_node(node.subject)
        self._emit(Opcode.DEFINE_NAME, self._name(subject_name))

        end_patches = []
        for case in node.cases:
            # Load subject, load pattern, compare
            self._emit(Opcode.LOAD_NAME, self._name(subject_name))
            self._compile_node(case.pattern)
            self._emit(Opcode.BINARY_OP, self._name("=="))
            skip_jump = self._emit(Opcode.JUMP_IF_FALSE, None)

            self._compile_node(case.body)
            end_patches.append(self._emit(Opcode.JUMP, None))

            self._patch(skip_jump, self._here())

        if node.default:
            self._compile_node(node.default)

        end_ip = self._here()
        for ep in end_patches:
            self._patch(ep, end_ip)

    # ── Expressions ───────────────────────────────────────────────────────────

    def _compile_IntLiteral(self, node: IntLiteral):
        self._emit(Opcode.LOAD_CONST, self._const(node.value))

    def _compile_FloatLiteral(self, node: FloatLiteral):
        self._emit(Opcode.LOAD_CONST, self._const(node.value))

    def _compile_StringLiteral(self, node: StringLiteral):
        self._emit(Opcode.LOAD_CONST, self._const(node.value))

    def _compile_BoolLiteral(self, node: BoolLiteral):
        self._emit(Opcode.LOAD_CONST, self._const(node.value))

    def _compile_NullLiteral(self, node: NullLiteral):
        self._emit(Opcode.LOAD_CONST, self._const(None))

    def _compile_Identifier(self, node: Identifier):
        self._emit(Opcode.LOAD_NAME, self._name(node.name))

    def _compile_UnaryExpr(self, node: UnaryExpr):
        self._compile_node(node.operand)
        self._emit(Opcode.UNARY_OP, self._name(node.operator))

    def _compile_BinaryExpr(self, node: BinaryExpr):
        # Short-circuit: and / or
        if node.operator == "and":
            self._compile_node(node.left)
            jump = self._emit(Opcode.JUMP_IF_FALSE_PEEK, None)
            self._emit(Opcode.POP_TOP)
            self._compile_node(node.right)
            self._patch(jump, self._here())
            return
        if node.operator == "or":
            self._compile_node(node.left)
            jump = self._emit(Opcode.JUMP_IF_TRUE_PEEK, None)
            self._emit(Opcode.POP_TOP)
            self._compile_node(node.right)
            self._patch(jump, self._here())
            return

        self._compile_node(node.left)
        self._compile_node(node.right)
        self._emit(Opcode.BINARY_OP, self._name(node.operator))

    def _compile_CallExpr(self, node: CallExpr):
        self._compile_node(node.callee)
        for arg in node.arguments:
            self._compile_node(arg)
        self._emit(Opcode.CALL, len(node.arguments))

    def _compile_MemberExpr(self, node: MemberExpr):
        self._compile_node(node.object)
        self._emit(Opcode.LOAD_ATTR, self._name(node.property))

    def _compile_IndexExpr(self, node: IndexExpr):
        self._compile_node(node.object)
        self._compile_node(node.index)
        self._emit(Opcode.LOAD_INDEX)

    def _compile_RangeExpr(self, node: RangeExpr):
        self._compile_node(node.start)
        self._compile_node(node.end)
        if node.step:
            self._compile_node(node.step)
            self._emit(Opcode.BUILD_RANGE, 1)
        else:
            self._emit(Opcode.BUILD_RANGE, 0)

    def _compile_ListLiteral(self, node: ListLiteral):
        for el in node.elements:
            self._compile_node(el)
        self._emit(Opcode.BUILD_LIST, len(node.elements))

    def _compile_MapLiteral(self, node: MapLiteral):
        for k, v in node.pairs:
            self._compile_node(k)
            self._compile_node(v)
        self._emit(Opcode.BUILD_MAP, len(node.pairs))

    def _compile_SetLiteral(self, node: SetLiteral):
        for el in node.elements:
            self._compile_node(el)
        self._emit(Opcode.BUILD_SET, len(node.elements))

    def _compile_TupleLiteral(self, node: TupleLiteral):
        for el in node.elements:
            self._compile_node(el)
        self._emit(Opcode.BUILD_TUPLE, len(node.elements))

    # ── Peephole optimizer ────────────────────────────────────────────────────

    def _optimize(self) -> None:
        """Run peephole optimizations on the compiled bytecode in-place."""
        self._fold_constants()
        self._eliminate_dead_code()
        self._eliminate_nops()

    def _fold_constants(self) -> None:
        """Constant-fold binary operations on two adjacent LOAD_CONST instructions."""
        instrs = self._code.instructions
        consts = self._code.constants
        _BINARY_OPS = {"+", "-", "*", "/", "%", "**", "//"}
        i = 0
        while i < len(instrs) - 2:
            a = instrs[i]
            b = instrs[i + 1]
            op = instrs[i + 2]
            if (
                a.opcode == Opcode.LOAD_CONST
                and b.opcode == Opcode.LOAD_CONST
                and op.opcode == Opcode.BINARY_OP
            ):
                lv = consts[a.arg]
                rv = consts[b.arg]
                op_name = self._code.names[op.arg]
                if op_name in _BINARY_OPS and isinstance(lv, (int, float)) and isinstance(rv, (int, float)):
                    try:
                        if op_name == "+":   result = lv + rv
                        elif op_name == "-": result = lv - rv
                        elif op_name == "*": result = lv * rv
                        elif op_name == "/":
                            if rv == 0: i += 1; continue
                            result = lv / rv
                        elif op_name == "%":
                            if rv == 0: i += 1; continue
                            result = lv % rv
                        elif op_name == "**": result = lv ** rv
                        elif op_name == "//":
                            if rv == 0: i += 1; continue
                            result = lv // rv
                        else: i += 1; continue
                        # Replace with single LOAD_CONST, NOP, NOP
                        ridx = self._const(result)
                        instrs[i]     = Instruction(Opcode.LOAD_CONST, ridx)
                        instrs[i + 1] = Instruction(Opcode.NOP)
                        instrs[i + 2] = Instruction(Opcode.NOP)
                        # Don't advance i — the new LOAD_CONST might fold again
                        continue
                    except Exception:
                        pass
            i += 1

    def _eliminate_dead_code(self) -> None:
        """Iteratively identify and remove unreachable instructions after RETURN, JUMP, or RAISE."""
        instrs = self._code.instructions
        if not instrs:
            return

        _JUMP_OPS = {
            Opcode.JUMP, Opcode.JUMP_IF_FALSE, Opcode.JUMP_IF_TRUE,
            Opcode.JUMP_IF_FALSE_PEEK, Opcode.JUMP_IF_TRUE_PEEK,
            Opcode.FOR_ITER, Opcode.SETUP_EXCEPT,
        }
        _TERMINATORS = {Opcode.RETURN, Opcode.JUMP, Opcode.RAISE}

        while True:
            # 1. Collect active (non-NOP) jump targets
            referenced_ips = set()
            for i, instr in enumerate(instrs):
                if instr.opcode in _JUMP_OPS and instr.opcode != Opcode.NOP and instr.arg is not None:
                    referenced_ips.add(instr.arg)

            # 2. Mark unreachable instructions as NOP
            changed = False
            is_dead = False
            for i in range(len(instrs)):
                if i in referenced_ips:
                    is_dead = False
                
                if is_dead:
                    if instrs[i].opcode != Opcode.NOP:
                        instrs[i] = Instruction(Opcode.NOP)
                        changed = True
                elif instrs[i].opcode in _TERMINATORS:
                    is_dead = True
            
            if not changed:
                break

    def _eliminate_nops(self) -> None:
        """Remove NOP instructions and patch all jump targets accordingly."""
        instrs = self._code.instructions
        # Build old_ip → new_ip mapping
        ip_map: dict[int, int] = {}
        new_ip = 0
        for old_ip, instr in enumerate(instrs):
            ip_map[old_ip] = new_ip
            if instr.opcode != Opcode.NOP:
                new_ip += 1
        # Also map one-past-end
        ip_map[len(instrs)] = new_ip

        _JUMP_OPS = {
            Opcode.JUMP, Opcode.JUMP_IF_FALSE, Opcode.JUMP_IF_TRUE,
            Opcode.JUMP_IF_FALSE_PEEK, Opcode.JUMP_IF_TRUE_PEEK,
            Opcode.FOR_ITER, Opcode.SETUP_EXCEPT,
        }
        # Remove NOPs and patch jumps
        new_instrs = []
        for instr in instrs:
            if instr.opcode == Opcode.NOP:
                continue
            if instr.opcode in _JUMP_OPS and instr.arg is not None:
                instr.arg = ip_map.get(instr.arg, instr.arg)
            new_instrs.append(instr)
        self._code.instructions = new_instrs

    # FStringLiteral is desugared to BinaryExpr by the parser; no handler needed.
