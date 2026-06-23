import os
from taipan.compiler.ast.nodes import *

class CTranspiler:
    def __init__(self):
        self.code = []
        self.indent_level = 0
        self.top_level_funcs = set()
        self.scopes = [set()]
        self.lambdas = []

    def indent(self):
        self.indent_level += 1

    def dedent(self):
        self.indent_level = max(0, self.indent_level - 1)

    def emit(self, line: str):
        indent_str = "    " * self.indent_level
        self.code.append(f"{indent_str}{line}")

    def get_op_func(self, op: str) -> str:
        mapping = {
            "+": "pee_add",
            "-": "pee_sub",
            "*": "pee_mul",
            "/": "pee_div",
            "%": "pee_mod",
            "**": "pee_pow",
            "==": "pee_eq",
            "!=": "pee_ne",
            "<": "pee_lt",
            "<=": "pee_le",
            ">": "pee_gt",
            ">=": "pee_ge",
        }
        if op in mapping:
            return mapping[op]
        raise NotImplementedError(f"Operator '{op}' not implemented in C backend")

    def visit(self, node: Node):
        if node is None:
            return "pee_null()"
        method_name = f"visit_{type(node).__name__}"
        visitor = getattr(self, method_name, None)
        if visitor is None:
            raise NotImplementedError(f"No visit_{type(node).__name__} method defined in CTranspiler")
        return visitor(node)

    def transpile(self, program: Program) -> str:
        # First pass: find all top-level functions to declare them forward
        for node in program.body:
            if isinstance(node, FunctionDecl):
                self.top_level_funcs.add(node.name)

        # Include runtime header
        self.emit('#include "taipan_runtime.h"')
        self.emit('')

        # Second pass: generate forward declarations for top-level functions
        for node in program.body:
            if isinstance(node, FunctionDecl):
                params_str = ", ".join(f"PeeValue {p.name}" for p in node.params)
                self.emit(f"PeeValue pee_func_{node.name}({params_str or 'void'});")
                self.emit(f"PeeValue pee_wrap_{node.name}(int arg_count, PeeValue* args);")

        self.emit('')

        # Temporarily compile main statements to self.code, but keep track of lambdas/functions
        func_bodies = []
        
        # We need to compile the function bodies first
        old_code = self.code
        for node in program.body:
            if isinstance(node, FunctionDecl):
                self.code = []
                self.visit(node)
                func_bodies.append("\n".join(self.code))
        
        # Compile main statements
        self.code = []
        self.emit('int main(int argc, char** argv) {')
        self.indent()
        
        # Declare top-level functions as PeeValue variables in main
        for f in self.top_level_funcs:
            self.emit(f'PeeValue {f} = pee_func(pee_wrap_{f}, "{f}");')

        for node in program.body:
            if not isinstance(node, FunctionDecl):
                self.visit(node)

        self.emit('return 0;')
        self.dedent()
        self.emit('}')
        main_body = "\n".join(self.code)

        # Generate wrappers
        wrappers = []
        for node in program.body:
            if isinstance(node, FunctionDecl):
                wrappers.append(f"PeeValue pee_wrap_{node.name}(int arg_count, PeeValue* args) {{")
                # Unpack arguments with null fallback
                unpack_lines = []
                for i, p in enumerate(node.params):
                    unpack_lines.append(f"PeeValue {p.name} = arg_count > {i} ? args[{i}] : pee_null();")
                # Call C function
                call_args = ", ".join(p.name for p in node.params)
                wrapper_body = f"    return pee_func_{node.name}({call_args});"
                wrappers.append("    " + "\n    ".join(unpack_lines) if unpack_lines else "")
                wrappers.append(wrapper_body)
                wrappers.append("}")
                wrappers.append("")

        # Re-assemble everything in correct order:
        # 1. Include + Decl
        # 2. Lambdas
        # 3. Function Bodies
        # 4. Main
        # 5. Wrappers
        final_code = []
        final_code.append("\n".join(old_code)) # Includes & forward declarations
        if self.lambdas:
            final_code.append("\n\n".join(self.lambdas))
            final_code.append("")
        if func_bodies:
            final_code.append("\n\n".join(func_bodies))
            final_code.append("")
        final_code.append(main_body)
        final_code.append("")
        if wrappers:
            final_code.append("\n".join(wrappers))

        return "\n".join(final_code)

    # ── Statement Visitors ───────────────────────────────────────────────────

    def visit_Program(self, node: Program):
        for stmt in node.body:
            self.visit(stmt)

    def visit_Block(self, node: Block):
        self.emit("{")
        self.indent()
        self.scopes.append(set())
        for stmt in node.statements:
            self.visit(stmt)
        self.scopes.pop()
        self.dedent()
        self.emit("}")

    def visit_FunctionDecl(self, node: FunctionDecl):
        params_str = ", ".join(f"PeeValue {p.name}" for p in node.params)
        self.emit(f"PeeValue pee_func_{node.name}({params_str or 'void'}) {{")
        self.indent()
        self.scopes.append(set())
        for stmt in node.body.statements:
            self.visit(stmt)
        self.emit("return pee_null();")
        self.scopes.pop()
        self.dedent()
        self.emit("}")

    def visit_ReturnStmt(self, node: ReturnStmt):
        val = self.visit(node.value) if node.value else "pee_null()"
        self.emit(f"return {val};")

    def visit_VariableDecl(self, node: VariableDecl):
        name = node.name
        val = self.visit(node.value) if node.value else "pee_null()"
        if name in self.scopes[-1]:
            self.emit(f"{name} = {val};")
        else:
            self.scopes[-1].add(name)
            self.emit(f"PeeValue {name} = {val};")

    def visit_ConstDecl(self, node: ConstDecl):
        name = node.name
        val = self.visit(node.value)
        if name in self.scopes[-1]:
            self.emit(f"{name} = {val};")
        else:
            self.scopes[-1].add(name)
            self.emit(f"PeeValue {name} = {val};")

    def visit_AssignStmt(self, node: AssignStmt):
        val = self.visit(node.value)
        if isinstance(node.target, IndexExpr):
            obj = self.visit(node.target.object)
            idx = self.visit(node.target.index)
            if node.operator == "=":
                self.emit(f"pee_index_set({obj}, {idx}, {val});")
            else:
                op = node.operator[:-1]
                op_func = self.get_op_func(op)
                self.emit(f"pee_index_set({obj}, {idx}, {op_func}(pee_index_get({obj}, {idx}), {val}));")
        else:
            target = self.visit(node.target)
            if node.operator == "=":
                self.emit(f"{target} = {val};")
            else:
                op = node.operator[:-1]
                op_func = self.get_op_func(op)
                self.emit(f"{target} = {op_func}({target}, {val});")

    def visit_IfStmt(self, node: IfStmt):
        cond = self.visit(node.condition)
        self.emit(f"if (pee_truthy({cond})) {{")
        self.indent()
        self.scopes.append(set())
        for stmt in node.then_branch.statements:
            self.visit(stmt)
        self.scopes.pop()
        self.dedent()
        self.emit("}")
        if node.else_branch:
            self.emit("else {")
            self.indent()
            self.scopes.append(set())
            if isinstance(node.else_branch, IfStmt):
                self.visit(node.else_branch)
            else:
                for stmt in node.else_branch.statements:
                    self.visit(stmt)
            self.scopes.pop()
            self.dedent()
            self.emit("}")

    def visit_WhileStmt(self, node: WhileStmt):
        cond = self.visit(node.condition)
        self.emit(f"while (pee_truthy({cond})) {{")
        self.indent()
        self.scopes.append(set())
        for stmt in node.body.statements:
            self.visit(stmt)
        self.scopes.pop()
        self.dedent()
        self.emit("}")

    def visit_ForStmt(self, node: ForStmt):
        iterable = self.visit(node.iterable)
        self.emit("{")
        self.indent()
        self.scopes.append(set())
        self.emit(f"PeeValue _iter = {iterable};")
        self.emit("if (_iter.type == VAL_RANGE) {")
        self.indent()
        self.emit("long long _start = _iter.range_val.start;")
        self.emit("long long _end = _iter.range_val.end;")
        self.emit("long long _step = _iter.range_val.step;")
        self.emit("bool _inc = _iter.range_val.inclusive;")
        self.emit("for (long long _val = _start; _inc ? (_step > 0 ? _val <= _end : _val >= _end) : (_step > 0 ? _val < _end : _val > _end); _val += _step) {")
        self.indent()
        self.emit(f"PeeValue {node.variable} = pee_int(_val);")
        for stmt in node.body.statements:
            self.visit(stmt)
        self.dedent()
        self.emit("}")
        self.dedent()
        self.emit("} else if (_iter.type == VAL_LIST) {")
        self.indent()
        self.emit("for (int _i = 0; _i < _iter.list_val->length; _i++) {")
        self.indent()
        self.emit(f"PeeValue {node.variable} = _iter.list_val->data[_i];")
        for stmt in node.body.statements:
            self.visit(stmt)
        self.dedent()
        self.emit("}")
        self.dedent()
        self.emit("} else if (_iter.type == VAL_STRING) {")
        self.indent()
        self.emit("for (int _i = 0; _i < strlen(_iter.string_val); _i++) {")
        self.indent()
        self.emit("char _tmp[2] = { _iter.string_val[_i], '\\0' };")
        self.emit(f"PeeValue {node.variable} = pee_string(_tmp);")
        for stmt in node.body.statements:
            self.visit(stmt)
        self.dedent()
        self.emit("}")
        self.dedent()
        self.emit("}")
        self.scopes.pop()
        self.dedent()
        self.emit("}")

    def visit_RepeatStmt(self, node: RepeatStmt):
        count = self.visit(node.count)
        self.emit("{")
        self.indent()
        self.scopes.append(set())
        self.emit(f"PeeValue _count_val = {count};")
        self.emit("long long _count = (_count_val.type == VAL_INT) ? _count_val.int_val : 0;")
        self.emit("for (long long _r = 0; _r < _count; _r++) {")
        self.indent()
        for stmt in node.body.statements:
            self.visit(stmt)
        self.dedent()
        self.emit("}")
        self.scopes.pop()
        self.dedent()
        self.emit("}")

    def visit_BreakStmt(self, node: BreakStmt):
        self.emit("break;")

    def visit_ContinueStmt(self, node: ContinueStmt):
        self.emit("continue;")

    def visit_ExpressionStmt(self, node: ExpressionStmt):
        expr = self.visit(node.expression)
        self.emit(f"{expr};")

    def visit_MatchStmt(self, node: MatchStmt):
        subject = self.visit(node.subject)
        self.emit("{")
        self.indent()
        self.scopes.append(set())
        self.emit(f"PeeValue _subject = {subject};")
        self.emit("bool _matched = false;")
        for case in node.cases:
            pattern = self.visit(case.pattern)
            self.emit(f"if (!_matched && pee_eq_c(_subject, {pattern})) {{")
            self.indent()
            self.emit("_matched = true;")
            self.scopes.append(set())
            for stmt in case.body.statements:
                self.visit(stmt)
            self.scopes.pop()
            self.dedent()
            self.emit("}")
        if node.default:
            self.emit("if (!_matched) {")
            self.indent()
            self.scopes.append(set())
            for stmt in node.default.statements:
                self.visit(stmt)
            self.scopes.pop()
            self.dedent()
            self.emit("}")
        self.scopes.pop()
        self.dedent()
        self.emit("}")

    def visit_TryCatchStmt(self, node: TryCatchStmt):
        raise NotImplementedError("Try/Catch is not yet supported in AOT C compiler backend.")

    def visit_SpawnStmt(self, node: SpawnStmt):
        raise NotImplementedError("Spawn is not yet supported in AOT C compiler backend.")

    def visit_WaitStmt(self, node: WaitStmt):
        raise NotImplementedError("Wait is not yet supported in AOT C compiler backend.")

    def visit_AiDeclStmt(self, node: AiDeclStmt):
        raise NotImplementedError("AI is not yet supported in AOT C compiler backend.")

    def visit_TestStmt(self, node: TestStmt):
        # We can just ignore test blocks when compiling, or wrap them. Let's ignore them.
        pass

    # ── Expression Visitors ──────────────────────────────────────────────────

    def visit_IntLiteral(self, node: IntLiteral) -> str:
        return f"pee_int({node.value})"

    def visit_FloatLiteral(self, node: FloatLiteral) -> str:
        return f"pee_float({node.value})"

    def visit_StringLiteral(self, node: StringLiteral) -> str:
        escaped = node.value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
        return f'pee_string("{escaped}")'

    def visit_FStringLiteral(self, node: FStringLiteral) -> str:
        if not node.parts:
            return 'pee_string("")'
        exprs = []
        for kind, val in node.parts:
            if kind == 'lit':
                escaped = val.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
                exprs.append(f'pee_string("{escaped}")')
            else:
                exprs.append(self.visit(val))
        res = exprs[0]
        for other in exprs[1:]:
            res = f"pee_add({res}, {other})"
        return res

    def visit_BoolLiteral(self, node: BoolLiteral) -> str:
        return f"pee_bool({str(node.value).lower()})"

    def visit_NullLiteral(self, node: NullLiteral) -> str:
        return "pee_null()"

    def visit_Identifier(self, node: Identifier) -> str:
        return node.name

    def visit_ListLiteral(self, node: ListLiteral) -> str:
        if not node.elements:
            return "pee_list_new()"
        appends = []
        for e in node.elements:
            val = self.visit(e)
            appends.append(f"pee_list_append(_list, {val});")
        appends_str = " ".join(appends)
        return f"({{ PeeValue _list = pee_list_new(); {appends_str} _list; }})"

    def visit_BinaryExpr(self, node: BinaryExpr) -> str:
        left = self.visit(node.left)
        right = self.visit(node.right)
        op = node.operator
        if op == 'and':
            return f"({{ PeeValue _l = {left}; pee_truthy(_l) ? {right} : _l; }})"
        if op == 'or':
            return f"({{ PeeValue _l = {left}; pee_truthy(_l) ? _l : {right}; }})"
        op_func = self.get_op_func(op)
        return f"{op_func}({left}, {right})"

    def visit_UnaryExpr(self, node: UnaryExpr) -> str:
        operand = self.visit(node.operand)
        if node.operator == '-':
            return f"pee_neg({operand})"
        if node.operator == 'not':
            return f"pee_bool(!pee_truthy({operand}))"
        raise NotImplementedError(f"Unary operator '{node.operator}' not implemented")

    def visit_RangeExpr(self, node: RangeExpr) -> str:
        start = self.visit(node.start)
        end = self.visit(node.end)
        step = self.visit(node.step) if node.step else "pee_int(1)"
        inc_str = "true" if node.inclusive else "false"
        return f"pee_range({start}.int_val, {end}.int_val, {step}.int_val, {inc_str})"

    def visit_IndexExpr(self, node: IndexExpr) -> str:
        obj = self.visit(node.object)
        idx = self.visit(node.index)
        return f"pee_index_get({obj}, {idx})"

    def visit_MemberExpr(self, node: MemberExpr) -> str:
        # Evaluated member property.
        # Normally accessed via methods. If standalone, we just warning / return null
        return f"pee_null()"

    def visit_CallExpr(self, node: CallExpr) -> str:
        # Check member call (like obj.append(x))
        if isinstance(node.callee, MemberExpr):
            obj = self.visit(node.callee.object)
            prop = node.callee.property
            if prop in ("append", "push"):
                arg = self.visit(node.arguments[0])
                return f"({{ pee_list_append({obj}, {arg}); pee_null(); }})"

        # Direct call check
        if isinstance(node.callee, Identifier):
            name = node.callee.name
            if name in ("show", "print"):
                args_str = ", ".join(self.visit(arg) for arg in node.arguments)
                return f"({{ pee_show({len(node.arguments)}, {args_str}); pee_null(); }})"
            if name == "str":
                arg = self.visit(node.arguments[0])
                return f"pee_str_fn({arg})"
            if name == "int":
                arg = self.visit(node.arguments[0])
                return f"pee_int_fn({arg})"
            if name == "float":
                arg = self.visit(node.arguments[0])
                return f"pee_float_fn({arg})"
            if name == "bool":
                arg = self.visit(node.arguments[0])
                return f"pee_bool_fn({arg})"
            if name == "len":
                arg = self.visit(node.arguments[0])
                return f"pee_len_fn({arg})"
            if name == "input":
                arg = self.visit(node.arguments[0]) if node.arguments else "pee_null()"
                return f"pee_input_fn({arg})"
            if name in self.top_level_funcs:
                args_str = ", ".join(self.visit(arg) for arg in node.arguments)
                return f"pee_func_{name}({args_str})"

        # Dynamic call
        callee = self.visit(node.callee)
        args_list = [self.visit(arg) for arg in node.arguments]
        args_str = ", ".join(args_list)
        if args_list:
            return f"pee_call_dynamic({callee}, {len(args_list)}, {args_str})"
        else:
            return f"pee_call_dynamic({callee}, 0)"

    def visit_LambdaExpr(self, node: LambdaExpr) -> str:
        lambda_id = len(self.lambdas) + 1
        lambda_name = f"pee_lambda_{lambda_id}"
        
        params_unpack = []
        for i, p in enumerate(node.params):
            params_unpack.append(f"PeeValue {p.name} = arg_count > {i} ? args[{i}] : pee_null();")
        params_unpack_str = "\n    ".join(params_unpack)
        
        body_expr = self.visit(node.body)
        
        lambda_code = f"""PeeValue {lambda_name}(int arg_count, PeeValue* args) {{
    {params_unpack_str}
    return {body_expr};
}}"""
        self.lambdas.append(lambda_code)
        
        return f'pee_func({lambda_name}, "<lambda>")'

    def visit_MapLiteral(self, node: MapLiteral) -> str:
        raise NotImplementedError("Map literals not implemented in AOT C backend yet.")

    def visit_SetLiteral(self, node: SetLiteral) -> str:
        raise NotImplementedError("Set literals not implemented in AOT C backend yet.")

    def visit_TupleLiteral(self, node: TupleLiteral) -> str:
        raise NotImplementedError("Tuple literals not implemented in AOT C backend yet.")
