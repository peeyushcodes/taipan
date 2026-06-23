from __future__ import annotations
from typing import List, Optional, Any
from taipan.compiler.ast.nodes import *
from taipan.runtime.errors import TaipanSemanticError


class FunctionType:
    def __init__(self, param_types: List[str], return_type: str, type_parameters: List[str] = None):
        self.param_types = param_types
        self.return_type = return_type
        self.type_parameters = type_parameters or []

    def __repr__(self):
        type_params = f"<{', '.join(self.type_parameters)}>" if self.type_parameters else ""
        return f"{type_params}({', '.join(self.param_types)}) -> {self.return_type}"


class TypeEnvironment:
    def __init__(self, parent: Optional[TypeEnvironment] = None):
        self._types: dict[str, Any] = {}
        self.parent = parent

    def define(self, name: str, type_val: Any):
        self._types[name] = type_val

    def lookup(self, name: str) -> Any:
        if name in self._types:
            return self._types[name]
        if self.parent:
            return self.parent.lookup(name)
        return "Any"


# Builtin function mappings to their signatures
BUILTIN_FUNCS = {
    "show":     FunctionType([], "Null"),     # variadic Any
    "print":    FunctionType([], "Null"),     # variadic Any
    "len":      FunctionType(["Any"], "Int"),
    "str":      FunctionType(["Any"], "String"),
    "int":      FunctionType(["Any"], "Int"),
    "float":    FunctionType(["Any"], "Float"),
    "bool":     FunctionType(["Any"], "Bool"),
    "type":     FunctionType(["Any"], "String"),
    "input":    FunctionType(["Any"], "String"),
    "range":    FunctionType(["Int", "Int", "Int"], "Range"),
    "abs":      FunctionType(["Any"], "Any"),
    "min":      FunctionType([], "Any"),
    "max":      FunctionType([], "Any"),
    "sum":      FunctionType([], "Any"),
    "round":    FunctionType(["Any"], "Any"),
    "sorted":   FunctionType(["List"], "List"),
    "reversed": FunctionType(["List"], "List"),
    "exit":     FunctionType(["Int"], "Null"),
}


class TypeChecker:
    def __init__(self):
        self.errors: List[TaipanSemanticError] = []
        self.env = TypeEnvironment()
        self.current_return_type = "Any"
        self._return_type_stack: List[List[Any]] = []

        # Pre-populate builtin function signatures
        for name, sig in BUILTIN_FUNCS.items():
            self.env.define(name, sig)

    def _resolve_type(self, type_annot: Any) -> str:
        if type_annot is None:
            return "Any"
        if isinstance(type_annot, str):
            return type_annot
        if isinstance(type_annot, SimpleType):
            return type_annot.name
        if isinstance(type_annot, GenericType):
            params_str = ", ".join(self._resolve_type(p) for p in type_annot.params)
            return f"{type_annot.name}<{params_str}>"
        return "Any"

    def _split_generic(self, type_str: str) -> tuple[str, List[str]]:
        if "<" not in type_str:
            return type_str, []
        idx = type_str.index("<")
        name = type_str[:idx].strip()
        rest = type_str[idx+1:]
        if rest.endswith(">"):
            rest = rest[:-1]
        
        args = []
        depth = 0
        current = []
        for char in rest:
            if char == "<":
                depth += 1
                current.append(char)
            elif char == ">":
                depth -= 1
                current.append(char)
            elif char == "," and depth == 0:
                args.append("".join(current).strip())
                current = []
            else:
                current.append(char)
        if current:
            args.append("".join(current).strip())
        return name, args

    def _unify_type_vars(self, param_type: str, arg_type: str, type_params: List[str], bindings: dict[str, str]) -> None:
        if param_type in type_params:
            if param_type in bindings:
                bindings[param_type] = self._unify_types([bindings[param_type], arg_type])
            else:
                bindings[param_type] = arg_type
            return

        if "<" in param_type and "<" in arg_type:
            p_name, p_args = self._split_generic(param_type)
            a_name, a_args = self._split_generic(arg_type)
            if p_name == a_name and len(p_args) == len(a_args):
                for p_sub, a_sub in zip(p_args, a_args):
                    self._unify_type_vars(p_sub, a_sub, type_params, bindings)

    def _substitute_type(self, type_str: str, bindings: dict[str, str]) -> str:
        if type_str in bindings:
            return bindings[type_str]
        
        if "<" in type_str:
            name, args = self._split_generic(type_str)
            subbed_args = [self._substitute_type(arg, bindings) for arg in args]
            return f"{name}<{', '.join(subbed_args)}>"
            
        return type_str

    def _unify_types(self, types: List[Any]) -> Any:
        """Compute the most specific common type of a list of types."""
        if not types:
            return "Null"
        
        current = types[0]
        for t in types[1:]:
            if current == t:
                continue
            if current == "Any":
                current = t
            elif t == "Any":
                pass
            elif current == "Null":
                current = t
            elif t == "Null":
                pass
            elif current == "Int" and t == "Float":
                current = "Float"
            elif current == "Float" and t == "Int":
                current = "Float"
            elif isinstance(current, FunctionType) and isinstance(t, FunctionType):
                if repr(current) == repr(t):
                    continue
                current = "Any"
            else:
                current = "Any"
        return current

    def is_compatible(self, actual: Any, expected: Any) -> bool:
        actual = self._resolve_type(actual)
        expected = self._resolve_type(expected)

        if actual == "Any" or expected == "Any":
            return True
        # Widening: Int -> Float
        if actual == "Int" and expected == "Float":
            return True
        if isinstance(actual, FunctionType) and isinstance(expected, FunctionType):
            if len(actual.param_types) != len(expected.param_types):
                return False
            for a_p, e_p in zip(actual.param_types, expected.param_types):
                if not self.is_compatible(e_p, a_p):  # Contra-variant params
                    return False
            return self.is_compatible(actual.return_type, expected.return_type) # Co-variant returns
            
        # Check generic compatibility
        if "<" in actual or "<" in expected:
            act_name, act_args = self._split_generic(actual)
            exp_name, exp_args = self._split_generic(expected)
            if act_name != exp_name:
                return False
            if not act_args or not exp_args:
                return True
            if len(act_args) != len(exp_args):
                return False
            return all(self.is_compatible(a, e) for a, e in zip(act_args, exp_args))

        return actual == expected

    def check(self, program: Program) -> List[TaipanSemanticError]:
        self.visit(program)
        return self.errors

    def visit(self, node: Node) -> Any:
        if node is None:
            return "Null"
        method_name = f"visit_{type(node).__name__}"
        visitor = getattr(self, method_name, None)
        if visitor is None:
            # Fallback: visit all child nodes
            for attr in vars(node).values():
                if isinstance(attr, Node):
                    self.visit(attr)
                elif isinstance(attr, list):
                    for item in attr:
                        if isinstance(item, Node):
                            self.visit(item)
            return "Any"
        return visitor(node)

    # ── Statement Visitors ───────────────────────────────────────────────────

    def visit_Program(self, node: Program):
        # Register all top-level functions first for forward references
        for stmt in node.body:
            if isinstance(stmt, FunctionDecl):
                param_types = [self._resolve_type(p.type_hint) for p in stmt.params]
                ret_type = self._resolve_type(stmt.return_type)
                if stmt.is_async:
                    ret_type = f"Promise<{ret_type}>"
                self.env.define(stmt.name, FunctionType(param_types, ret_type, type_parameters=stmt.type_parameters))

        for stmt in node.body:
            self.visit(stmt)

    def visit_Block(self, node: Block):
        parent_env = self.env
        self.env = TypeEnvironment(parent=parent_env)
        for stmt in node.statements:
            self.visit(stmt)
        self.env = parent_env

    def visit_FunctionDecl(self, node: FunctionDecl):
        parent_env = self.env
        self.env = TypeEnvironment(parent=parent_env)

        inferred_param_types = []
        for param in node.params:
            p_type = self._resolve_type(param.type_hint)
            if param.default:
                def_type = self.visit(param.default)
                if p_type == "Any":
                    p_type = def_type
                elif not self.is_compatible(def_type, p_type):
                    self.errors.append(TaipanSemanticError(
                        f"Parameter '{param.name}' default type '{def_type}' is incompatible with type hint '{p_type}'",
                        param.line, param.column
                    ))
            self.env.define(param.name, p_type)
            inferred_param_types.append(p_type)

        old_return = self.current_return_type
        self.current_return_type = self._resolve_type(node.return_type)

        self._return_type_stack.append([])
        self.visit(node.body)
        inferred_returns = self._return_type_stack.pop()

        inferred_ret_type = self._resolve_type(node.return_type)
        if node.return_type is None:
            inferred_ret_type = self._unify_types(inferred_returns)

        # Update the function signature in the parent environment
        func_type = parent_env.lookup(node.name)
        if func_type == "Any" or not isinstance(func_type, FunctionType):
            ret_sig_type = f"Promise<{inferred_ret_type}>" if node.is_async else inferred_ret_type
            func_type = FunctionType(inferred_param_types, ret_sig_type, type_parameters=node.type_parameters)
            parent_env.define(node.name, func_type)
        else:
            func_type.param_types = inferred_param_types
            if node.return_type is None:
                if node.is_async:
                    func_type.return_type = f"Promise<{inferred_ret_type}>"
                else:
                    func_type.return_type = inferred_ret_type

        self.current_return_type = old_return
        self.env = parent_env

    def visit_ReturnStmt(self, node: ReturnStmt):
        ret_type = self.visit(node.value) if node.value else "Null"
        if self._return_type_stack:
            self._return_type_stack[-1].append(ret_type)
        if not self.is_compatible(ret_type, self.current_return_type):
            self.errors.append(TaipanSemanticError(
                f"Incompatible return type: declared '{self.current_return_type}', got '{ret_type}'",
                node.line, node.column
            ))

    def visit_VariableDecl(self, node: VariableDecl):
        expected_type = self._resolve_type(node.type_hint)
        if node.value:
            val_type = self.visit(node.value)
            if expected_type != "Any":
                if not self.is_compatible(val_type, expected_type):
                    self.errors.append(TaipanSemanticError(
                        f"Type mismatch: cannot assign value of type '{val_type}' to variable '{node.name}' of type '{expected_type}'",
                        node.line, node.column
                    ))
                self.env.define(node.name, expected_type)
            else:
                self.env.define(node.name, val_type)
        else:
            self.env.define(node.name, expected_type)

    def visit_ConstDecl(self, node: ConstDecl):
        val_type = self.visit(node.value)
        self.env.define(node.name, val_type)

    def visit_AssignStmt(self, node: AssignStmt):
        val_type = self.visit(node.value)
        if isinstance(node.target, Identifier):
            var_type = self.env.lookup(node.target.name)
            if var_type != "Any":
                if not self.is_compatible(val_type, var_type):
                    self.errors.append(TaipanSemanticError(
                        f"Type mismatch: cannot assign type '{val_type}' to variable '{node.target.name}' of type '{var_type}'",
                        node.line, node.column
                    ))
        elif isinstance(node.target, IndexExpr):
            self.visit(node.target)
        else:
            self.visit(node.target)

    def visit_IfStmt(self, node: IfStmt):
        self.visit(node.condition)
        self.visit(node.then_branch)
        if node.else_branch:
            self.visit(node.else_branch)

    def visit_WhileStmt(self, node: WhileStmt):
        self.visit(node.condition)
        self.visit(node.body)

    def visit_ForStmt(self, node: ForStmt):
        iter_type = self.visit(node.iterable)
        var_type = "Any"
        if iter_type == "Range":
            var_type = "Int"
        elif iter_type == "String":
            var_type = "String"

        parent_env = self.env
        self.env = TypeEnvironment(parent=parent_env)
        self.env.define(node.variable, var_type)
        self.visit(node.body)
        self.env = parent_env

    def visit_RepeatStmt(self, node: RepeatStmt):
        count_type = self.visit(node.count)
        if not self.is_compatible(count_type, "Int"):
            self.errors.append(TaipanSemanticError(
                f"Repeat count must be an Int, got '{count_type}'",
                node.line, node.column
            ))
        self.visit(node.body)

    def visit_ExpressionStmt(self, node: ExpressionStmt):
        self.visit(node.expression)

    def visit_MatchStmt(self, node: MatchStmt):
        self.visit(node.subject)
        for case in node.cases:
            self.visit(case)
        if node.default:
            self.visit(node.default)

    def visit_MatchCase(self, node: MatchCase):
        self.visit(node.pattern)
        self.visit(node.body)

    def visit_TryCatchStmt(self, node: TryCatchStmt):
        parent_env = self.env
        self.env = TypeEnvironment(parent=parent_env)
        self.env.define(node.error_var, "Any")
        self.visit(node.try_block)
        self.visit(node.catch_block)
        self.env = parent_env

    def visit_SpawnStmt(self, node: SpawnStmt):
        self.visit(node.expression)

    def visit_WaitStmt(self, node: WaitStmt):
        pass

    def visit_AiDeclStmt(self, node: AiDeclStmt):
        self.env.define(node.name, "AI")

    def visit_TestStmt(self, node: TestStmt):
        self.visit(node.body)

    def visit_BreakStmt(self, node: BreakStmt):
        pass

    def visit_ContinueStmt(self, node: ContinueStmt):
        pass

    # ── Expression Visitors ──────────────────────────────────────────────────

    def visit_IntLiteral(self, node: IntLiteral) -> str:
        return "Int"

    def visit_FloatLiteral(self, node: FloatLiteral) -> str:
        return "Float"

    def visit_StringLiteral(self, node: StringLiteral) -> str:
        return "String"

    def visit_BoolLiteral(self, node: BoolLiteral) -> str:
        return "Bool"

    def visit_NullLiteral(self, node: NullLiteral) -> str:
        return "Null"

    def visit_Identifier(self, node: Identifier) -> Any:
        return self.env.lookup(node.name)

    def visit_ListLiteral(self, node: ListLiteral) -> str:
        for el in node.elements:
            self.visit(el)
        return "List"

    def visit_BinaryExpr(self, node: BinaryExpr) -> str:
        left_t = self.visit(node.left)
        right_t = self.visit(node.right)
        op = node.operator

        if op in ("+", "-", "*", "/", "%", "**"):
            if op == "+":
                if left_t == "String" or right_t == "String":
                    return "String"
                if left_t == "List" and right_t == "List":
                    return "List"
            if op == "*":
                if (left_t == "String" and right_t == "Int") or (left_t == "Int" and right_t == "String"):
                    return "String"
            if op == "/":
                return "Float"

            if left_t == "Any" or right_t == "Any":
                return "Any"
            if left_t in ("Int", "Float") and right_t in ("Int", "Float"):
                if left_t == "Float" or right_t == "Float":
                    return "Float"
                return "Int"

            self.errors.append(TaipanSemanticError(
                f"Operator '{op}' cannot be applied to types '{left_t}' and '{right_t}'",
                node.line, node.column
            ))
            return "Any"

        if op in ("<", "<=", ">", ">=", "==", "!="):
            return "Bool"

        if op in ("and", "or"):
            return "Bool"

        return "Any"

    def visit_UnaryExpr(self, node: UnaryExpr) -> str:
        op = node.operator
        t = self.visit(node.operand)
        if op == "-":
            if t not in ("Int", "Float", "Any"):
                self.errors.append(TaipanSemanticError(
                    f"Operator '-' cannot be applied to type '{t}'",
                    node.line, node.column
                ))
            return t
        if op == "not":
            return "Bool"
        return "Any"

    def visit_RangeExpr(self, node: RangeExpr) -> str:
        start_t = self.visit(node.start)
        end_t = self.visit(node.end)
        if not self.is_compatible(start_t, "Int") or not self.is_compatible(end_t, "Int"):
            self.errors.append(TaipanSemanticError(
                f"Range boundaries must be Int, got '{start_t}' and '{end_t}'",
                node.line, node.column
            ))
        if node.step:
            step_t = self.visit(node.step)
            if not self.is_compatible(step_t, "Int"):
                self.errors.append(TaipanSemanticError(
                    f"Range step must be Int, got '{step_t}'",
                    node.line, node.column
                ))
        return "Range"

    def visit_IndexExpr(self, node: IndexExpr) -> str:
        obj_t = self.visit(node.object)
        idx_t = self.visit(node.index)
        if obj_t in ("List", "String", "Tuple", "Any"):
            if not self.is_compatible(idx_t, "Int"):
                self.errors.append(TaipanSemanticError(
                    f"Index must be Int for type '{obj_t}', got '{idx_t}'",
                    node.line, node.column
                ))
            if obj_t == "String":
                return "String"
            return "Any"
        self.errors.append(TaipanSemanticError(
            f"Type '{obj_t}' is not subscriptable",
            node.line, node.column
        ))
        return "Any"

    def visit_CallExpr(self, node: CallExpr) -> str:
        if isinstance(node.callee, MemberExpr):
            obj_t = self.visit(node.callee.object)
            prop = node.callee.property
            if obj_t.startswith("List") and prop in ("append", "push"):
                name, args = self._split_generic(obj_t)
                expected_item_t = args[0] if args else "Any"
                if len(node.arguments) != 1:
                    self.errors.append(TaipanSemanticError(
                        f"List.{prop}() takes exactly 1 argument, got {len(node.arguments)}",
                        node.line, node.column
                    ))
                else:
                    arg_t = self.visit(node.arguments[0])
                    if not self.is_compatible(arg_t, expected_item_t):
                        self.errors.append(TaipanSemanticError(
                            f"Argument type mismatch: expected '{expected_item_t}', got '{arg_t}'",
                            node.line, node.column
                        ))
                return "Null"
            for arg in node.arguments:
                self.visit(arg)
            return "Any"

        callee_t = self.visit(node.callee)
        args_types = [self.visit(arg) for arg in node.arguments]

        if isinstance(callee_t, FunctionType):
            # Verify argument count (builtins like show/print are registered with 0 but are variadic,
            # so we skip arg check for them. Standard show/print are BUILTIN_FUNCS with return 'Null')
            is_show = isinstance(node.callee, Identifier) and node.callee.name in ("show", "print")
            if not is_show and len(args_types) != len(callee_t.param_types):
                self.errors.append(TaipanSemanticError(
                    f"Argument count mismatch: function expected {len(callee_t.param_types)} arguments, got {len(args_types)}",
                    node.line, node.column
                ))
                return callee_t.return_type

            bindings = {}
            if callee_t.type_parameters:
                for param_t, arg_t in zip(callee_t.param_types, args_types):
                    self._unify_type_vars(param_t, arg_t, callee_t.type_parameters, bindings)
                for tp in callee_t.type_parameters:
                    if tp not in bindings:
                        bindings[tp] = "Any"
                resolved_param_types = [self._substitute_type(p_t, bindings) for p_t in callee_t.param_types]
                resolved_return_type = self._substitute_type(callee_t.return_type, bindings)
            else:
                resolved_param_types = callee_t.param_types
                resolved_return_type = callee_t.return_type

            if not is_show:
                for i, (arg_t, param_t) in enumerate(zip(args_types, resolved_param_types)):
                    if not self.is_compatible(arg_t, param_t):
                        self.errors.append(TaipanSemanticError(
                            f"Argument type mismatch at parameter {i + 1}: expected '{param_t}', got '{arg_t}'",
                            node.line, node.column
                        ))
            return resolved_return_type

        if callee_t == "Any":
            return "Any"

        self.errors.append(TaipanSemanticError(
            f"Type '{callee_t}' is not callable",
            node.line, node.column
        ))
        return "Any"

    def visit_AwaitExpr(self, node: AwaitExpr) -> str:
        expr_t = self.visit(node.expression)
        if expr_t == "Any":
            return "Any"
        if expr_t.startswith("Promise"):
            name, args = self._split_generic(expr_t)
            if args:
                return args[0]
            return "Any"
        return expr_t

    def visit_LambdaExpr(self, node: LambdaExpr) -> FunctionType:
        param_types = [p.type_hint or "Any" for p in node.params]
        parent_env = self.env
        self.env = TypeEnvironment(parent=parent_env)
        for param in node.params:
            self.env.define(param.name, param.type_hint or "Any")
        ret_t = self.visit(node.body)
        self.env = parent_env
        return FunctionType(param_types, ret_t)

    def visit_MemberExpr(self, node: MemberExpr) -> str:
        self.visit(node.object)
        return "Any"

    def visit_FStringLiteral(self, node: FStringLiteral) -> str:
        for kind, part in node.parts:
            if kind == "expr":
                self.visit(part)
        return "String"

    def visit_MapLiteral(self, node: MapLiteral) -> str:
        for k, v in node.pairs:
            self.visit(k)
            self.visit(v)
        return "Map"

    def visit_SetLiteral(self, node: SetLiteral) -> str:
        for el in node.elements:
            self.visit(el)
        return "Set"

    def visit_TupleLiteral(self, node: TupleLiteral) -> str:
        for el in node.elements:
            self.visit(el)
        return "Tuple"
