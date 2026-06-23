"""
Taipan Parser
==============
Recursive descent parser that transforms a flat list of Tokens into an AST.

Operator precedence (lowest → highest):
  1. Assignment              (=, +=, -=, *=, /=)
  2. Logical or              (or)
  3. Logical and             (and)
  4. Logical not             (not)
  5. Comparison              (==, !=, <, <=, >, >=, in)
  6. Addition / Subtraction  (+, -)
  7. Multiplication / Div    (*, /, //, %)
  8. Power                   (**)
  9. Unary                   (-, !)
  10. Postfix                (call, member, index)
  11. Primary                (literals, identifiers, grouped expr)
"""

from typing import List, Optional
from taipan.compiler.lexer.tokens import Token, TokenType
from taipan.compiler.ast.nodes import *
from taipan.runtime.errors import TaipanSyntaxError


class Parser:
    """Recursive-descent parser for Taipan."""

    def __init__(self, tokens: List[Token], filename: str = "<stdin>"):
        self.tokens   = tokens
        self.filename = filename
        self.pos      = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def parse(self) -> Program:
        """Parse the token list into a Program AST node."""
        body: List[Node] = []
        while not self._at_end():
            stmt = self._parse_statement()
            if stmt is not None:
                body.append(stmt)
        return Program(body=body, line=1, column=1)

    # ── Navigation helpers ────────────────────────────────────────────────────

    def _at_end(self) -> bool:
        return self._peek().type == TokenType.EOF

    def _peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        if not self._at_end():
            self.pos += 1
        return tok

    def _check(self, *types: TokenType) -> bool:
        return self._peek().type in types

    def _match(self, *types: TokenType) -> Optional[Token]:
        if self._peek().type in types:
            return self._advance()
        return None

    def _expect(self, ttype: TokenType, msg: str = "") -> Token:
        if self._peek().type == ttype:
            return self._advance()
        tok = self._peek()
        raise TaipanSyntaxError(
            msg or f"Expected {ttype.name} but got {tok.type.name} ({tok.value!r})",
            tok.line, tok.column
        )

    def _loc(self) -> dict:
        tok = self._peek()
        return {"line": tok.line, "column": tok.column}

    # ── Statements ────────────────────────────────────────────────────────────

    def _parse_statement(self) -> Optional[Node]:
        tok = self._peek()

        match tok.type:
            case TokenType.LET:
                return self._parse_var_decl()
            case TokenType.CONST:
                return self._parse_const_decl()
            case TokenType.FUNC:
                return self._parse_func_decl()
            case TokenType.ASYNC:
                self._advance()  # consume 'async'
                return self._parse_func_decl(is_async=True)
            case TokenType.CLASS:
                return self._parse_class_decl()
            case TokenType.IF:
                return self._parse_if()
            case TokenType.WHILE:
                return self._parse_while()
            case TokenType.FOR:
                return self._parse_for()
            case TokenType.REPEAT:
                return self._parse_repeat()
            case TokenType.RETURN:
                return self._parse_return()
            case TokenType.TRY:
                return self._parse_try_catch()
            case TokenType.IMPORT:
                return self._parse_import()
            case TokenType.SPAWN:
                return self._parse_spawn()
            case TokenType.WAIT:
                return self._parse_wait()
            case TokenType.AI:
                return self._parse_ai_decl()
            case TokenType.TEST:
                return self._parse_test()
            case TokenType.BREAK:
                self._advance()
                return BreakStmt(**self._loc())
            case TokenType.CONTINUE:
                self._advance()
                return ContinueStmt(**self._loc())
            case TokenType.MATCH:
                return self._parse_match()
            case _:
                return self._parse_expression_statement()

    def _parse_var_decl(self) -> VariableDecl:
        tok = self._expect(TokenType.LET)
        name_tok = self._expect(TokenType.IDENTIFIER, "Expected variable name after 'let'")
        type_hint = None
        if self._match(TokenType.COLON):
            type_hint = self._parse_type_annotation()
        value = None
        if self._match(TokenType.EQUALS):
            value = self._parse_expr()
        return VariableDecl(name=name_tok.value, value=value, type_hint=type_hint,
                            line=tok.line, column=tok.column)

    def _parse_const_decl(self) -> ConstDecl:
        tok = self._expect(TokenType.CONST)
        name_tok = self._expect(TokenType.IDENTIFIER, "Expected constant name after 'const'")
        self._expect(TokenType.EQUALS, "Expected '=' after constant name")
        value = self._parse_expr()
        return ConstDecl(name=name_tok.value, value=value, line=tok.line, column=tok.column)

    def _parse_func_decl(self, is_method: bool = False, is_async: bool = False) -> FunctionDecl:
        tok = self._expect(TokenType.FUNC)
        name_tok = self._expect(TokenType.IDENTIFIER, "Expected function name after 'func'")
        
        # Parse optional type parameters: func name<T, U>(...)
        type_params = []
        if self._match(TokenType.LT):
            while True:
                t_tok = self._expect(TokenType.IDENTIFIER, "Expected type parameter name")
                type_params.append(t_tok.value)
                if not self._match(TokenType.COMMA):
                    break
            self._expect(TokenType.GT, "Expected '>' after type parameters")
            
        self._expect(TokenType.LPAREN, "Expected '(' after function name")
        params = self._parse_params()
        self._expect(TokenType.RPAREN, "Expected ')' after parameters")
        ret_type = None
        if self._match(TokenType.ARROW):
            ret_type = self._parse_type_annotation()
        body = self._parse_block()
        return FunctionDecl(name=name_tok.value, params=params, body=body,
                            return_type=ret_type, is_method=is_method,
                            is_async=is_async, type_parameters=type_params,
                            line=tok.line, column=tok.column)

    def _parse_params(self) -> List[Param]:
        params: List[Param] = []
        if self._check(TokenType.RPAREN):
            return params
        while True:
            name_tok = self._expect(TokenType.IDENTIFIER, "Expected parameter name")
            type_hint = None
            default = None
            if self._match(TokenType.COLON):
                type_hint = self._parse_type_annotation()
            if self._match(TokenType.EQUALS):
                default = self._parse_expr()
            params.append(Param(name=name_tok.value, type_hint=type_hint, default=default,
                                line=name_tok.line, column=name_tok.column))
            if not self._match(TokenType.COMMA):
                break
        return params

    def _parse_class_decl(self) -> ClassDecl:
        tok = self._expect(TokenType.CLASS)
        name_tok = self._expect(TokenType.IDENTIFIER, "Expected class name")
        superclass = None
        if self._match(TokenType.EXTENDS):
            superclass = self._expect(TokenType.IDENTIFIER, "Expected superclass name").value
        body = self._parse_block()
        return ClassDecl(name=name_tok.value, body=body, superclass=superclass,
                         line=tok.line, column=tok.column)

    def _parse_if(self) -> IfStmt:
        tok = self._expect(TokenType.IF)
        condition   = self._parse_expr()
        then_branch = self._parse_block()
        else_branch = None
        if self._match(TokenType.ELSE):
            if self._check(TokenType.IF):
                else_branch = self._parse_if()
            else:
                else_branch = self._parse_block()
        return IfStmt(condition=condition, then_branch=then_branch, else_branch=else_branch,
                      line=tok.line, column=tok.column)

    def _parse_while(self) -> WhileStmt:
        tok = self._expect(TokenType.WHILE)
        condition = self._parse_expr()
        body      = self._parse_block()
        return WhileStmt(condition=condition, body=body, line=tok.line, column=tok.column)

    def _parse_for(self) -> ForStmt:
        tok      = self._expect(TokenType.FOR)
        var_tok  = self._expect(TokenType.IDENTIFIER, "Expected loop variable")
        self._expect(TokenType.IN, "Expected 'in' after loop variable")
        iterable = self._parse_expr()
        body     = self._parse_block()
        return ForStmt(variable=var_tok.value, iterable=iterable, body=body,
                       line=tok.line, column=tok.column)

    def _parse_repeat(self) -> RepeatStmt:
        tok   = self._expect(TokenType.REPEAT)
        count = self._parse_expr()
        body  = self._parse_block()
        return RepeatStmt(count=count, body=body, line=tok.line, column=tok.column)

    def _parse_return(self) -> ReturnStmt:
        tok   = self._expect(TokenType.RETURN)
        value = None
        if not self._check(TokenType.RBRACE, TokenType.EOF):
            value = self._parse_expr()
        return ReturnStmt(value=value, line=tok.line, column=tok.column)

    def _parse_try_catch(self) -> TryCatchStmt:
        tok       = self._expect(TokenType.TRY)
        try_block = self._parse_block()
        self._expect(TokenType.CATCH, "Expected 'catch' after try block")
        # Accept both:  catch e { }   and   catch (e) { }
        has_paren = self._match(TokenType.LPAREN)
        err_tok   = self._expect(TokenType.IDENTIFIER, "Expected error variable name")
        if has_paren:
            self._expect(TokenType.RPAREN, "Expected ')' after catch variable name")
        catch_blk = self._parse_block()
        return TryCatchStmt(try_block=try_block, error_var=err_tok.value, catch_block=catch_blk,
                            line=tok.line, column=tok.column)


    def _parse_import(self) -> ImportStmt:
        tok = self._expect(TokenType.IMPORT)
        # Python interop: import python "module_name"
        if self._check(TokenType.IDENTIFIER) and self._peek().value == "python":
            self._advance()  # consume 'python'
            mod_tok = self._expect(TokenType.STRING, "Expected Python module name as string after 'import python'")
            return ImportStmt(module=mod_tok.value, alias=None, backend="python", line=tok.line, column=tok.column)
        # Allow keywords that are also valid module names (e.g. 'ai')
        if self._check(TokenType.IDENTIFIER):
            name_tok = self._advance()
        elif self._check(TokenType.AI):
            name_tok = self._advance()
        else:
            raise TaipanSyntaxError("Expected module name after 'import'", self._peek().line, self._peek().column)
        parts = [name_tok.value]
        while self._check(TokenType.DOT):
            self._advance()
            parts.append(self._expect(TokenType.IDENTIFIER).value)
        module = ".".join(parts)
        alias = None
        # future: "as alias"
        return ImportStmt(module=module, alias=alias, backend="taipan", line=tok.line, column=tok.column)

    def _parse_spawn(self) -> SpawnStmt:
        tok  = self._expect(TokenType.SPAWN)
        expr = self._parse_expr()
        return SpawnStmt(expression=expr, line=tok.line, column=tok.column)

    def _parse_wait(self) -> WaitStmt:
        tok = self._expect(TokenType.WAIT)
        return WaitStmt(line=tok.line, column=tok.column)

    def _parse_ai_decl(self) -> AiDeclStmt:
        tok = self._expect(TokenType.AI)
        name_tok = self._expect(TokenType.IDENTIFIER, "Expected AI instance name after 'ai'")
        return AiDeclStmt(name=name_tok.value, line=tok.line, column=tok.column)

    def _parse_test(self) -> TestStmt:
        tok = self._expect(TokenType.TEST)
        name_tok = self._expect(TokenType.STRING, "Expected test name string after 'test'")
        body = self._parse_block()
        return TestStmt(name=name_tok.value, body=body, line=tok.line, column=tok.column)

    def _parse_match(self) -> MatchStmt:
        """match expr { case pat: { body } ... default: { body } }"""
        tok     = self._expect(TokenType.MATCH)
        subject = self._parse_expr()
        self._expect(TokenType.LBRACE, "Expected '{' after match expression")

        cases: List[MatchCase] = []
        default: Optional[Block] = None

        while not self._check(TokenType.RBRACE, TokenType.EOF):
            if self._check(TokenType.CASE):
                case_tok = self._advance()  # consume 'case'
                pattern  = self._parse_expr()
                self._expect(TokenType.COLON, "Expected ':' after case pattern")
                body = self._parse_block()
                cases.append(MatchCase(pattern=pattern, body=body,
                                       line=case_tok.line, column=case_tok.column))
            elif self._check(TokenType.DEFAULT):
                self._advance()  # consume 'default'
                self._expect(TokenType.COLON, "Expected ':' after 'default'")
                default = self._parse_block()
            else:
                break

        self._expect(TokenType.RBRACE, "Expected '}' to close match block")
        return MatchStmt(subject=subject, cases=cases, default=default,
                         line=tok.line, column=tok.column)

    def _parse_expression_statement(self) -> ExpressionStmt:
        loc  = self._loc()
        expr = self._parse_expr()
        # Consume optional semicolons
        self._match(TokenType.SEMICOLON)
        # Check for augmented assignment or plain assignment
        if self._check(TokenType.EQUALS, TokenType.PLUS_EQ, TokenType.MINUS_EQ,
                       TokenType.STAR_EQ, TokenType.SLASH_EQ):
            op_tok = self._advance()
            value  = self._parse_expr()
            self._match(TokenType.SEMICOLON)
            return AssignStmt(target=expr, value=value, operator=op_tok.value,
                              **loc)
        return ExpressionStmt(expression=expr, **loc)

    # ── Block ─────────────────────────────────────────────────────────────────

    def _parse_block(self) -> Block:
        tok  = self._expect(TokenType.LBRACE, "Expected '{' to start block")
        stmts: List[Node] = []
        while not self._check(TokenType.RBRACE, TokenType.EOF):
            stmt = self._parse_statement()
            if stmt is not None:
                # Inside a class body, func declarations become methods
                stmts.append(stmt)
        self._expect(TokenType.RBRACE, "Expected '}' to end block")
        return Block(statements=stmts, line=tok.line, column=tok.column)

    # ── Expressions ───────────────────────────────────────────────────────────

    def _parse_expr(self) -> Node:
        return self._parse_or()

    def _parse_or(self) -> Node:
        left = self._parse_and()
        while self._check(TokenType.OR):
            op  = self._advance()
            rhs = self._parse_and()
            left = BinaryExpr(left=left, operator="or", right=rhs,
                              line=op.line, column=op.column)
        return left

    def _parse_and(self) -> Node:
        left = self._parse_not()
        while self._check(TokenType.AND):
            op  = self._advance()
            rhs = self._parse_not()
            left = BinaryExpr(left=left, operator="and", right=rhs,
                              line=op.line, column=op.column)
        return left

    def _parse_not(self) -> Node:
        if self._check(TokenType.NOT, TokenType.BANG):
            op = self._advance()
            operand = self._parse_not()
            return UnaryExpr(operator="not", operand=operand,
                             line=op.line, column=op.column)
        return self._parse_comparison()

    def _parse_comparison(self) -> Node:
        left = self._parse_range_expr()
        while self._check(TokenType.EQ_EQ, TokenType.NOT_EQ,
                          TokenType.LT, TokenType.LT_EQ,
                          TokenType.GT, TokenType.GT_EQ,
                          TokenType.IN):
            op  = self._advance()
            rhs = self._parse_range_expr()
            left = BinaryExpr(left=left, operator=op.value, right=rhs,
                              line=op.line, column=op.column)
        return left

    def _parse_range_expr(self) -> Node:
        """Handle start..end range expressions."""
        left = self._parse_addition()
        if self._check(TokenType.DOT_DOT):
            tok = self._advance()  # consume '..'
            right = self._parse_addition()
            return RangeExpr(start=left, end=right, line=tok.line, column=tok.column)
        return left

    def _parse_addition(self) -> Node:
        left = self._parse_multiply()
        while self._check(TokenType.PLUS, TokenType.MINUS):
            op  = self._advance()
            rhs = self._parse_multiply()
            left = BinaryExpr(left=left, operator=op.value, right=rhs,
                              line=op.line, column=op.column)
        return left

    def _parse_multiply(self) -> Node:
        left = self._parse_power()
        while self._check(TokenType.STAR, TokenType.SLASH,
                          TokenType.SLASH_SLASH, TokenType.PERCENT):
            op  = self._advance()
            rhs = self._parse_power()
            left = BinaryExpr(left=left, operator=op.value, right=rhs,
                              line=op.line, column=op.column)
        return left

    def _parse_power(self) -> Node:
        base = self._parse_unary()
        if self._check(TokenType.STAR_STAR):
            op  = self._advance()
            exp = self._parse_power()  # right-associative
            return BinaryExpr(left=base, operator="**", right=exp,
                              line=op.line, column=op.column)
        return base

    def _parse_unary(self) -> Node:
        if self._check(TokenType.AWAIT):
            op = self._advance()
            return AwaitExpr(expression=self._parse_unary(),
                             line=op.line, column=op.column)
        if self._check(TokenType.MINUS):
            op = self._advance()
            return UnaryExpr(operator="-", operand=self._parse_unary(),
                             line=op.line, column=op.column)
        if self._check(TokenType.BANG):
            op = self._advance()
            return UnaryExpr(operator="!", operand=self._parse_unary(),
                             line=op.line, column=op.column)
        return self._parse_postfix()

    def _parse_postfix(self) -> Node:
        expr = self._parse_primary()
        while True:
            if self._check(TokenType.LPAREN):
                expr = self._parse_call(expr)
            elif self._check(TokenType.DOT):
                expr = self._parse_member(expr)
            elif self._check(TokenType.LBRACKET):
                expr = self._parse_index(expr)
            else:
                break
        return expr

    def _parse_call(self, callee: Node) -> CallExpr:
        tok = self._expect(TokenType.LPAREN)
        args: List[Node] = []
        if not self._check(TokenType.RPAREN):
            args.append(self._parse_expr())
            while self._match(TokenType.COMMA):
                args.append(self._parse_expr())
        self._expect(TokenType.RPAREN, "Expected ')' after arguments")
        return CallExpr(callee=callee, arguments=args, line=tok.line, column=tok.column)

    def _parse_member(self, obj: Node) -> MemberExpr:
        tok = self._expect(TokenType.DOT)
        prop = self._expect(TokenType.IDENTIFIER, "Expected property name after '.'")
        return MemberExpr(object=obj, property=prop.value, line=tok.line, column=tok.column)

    def _parse_index(self, obj: Node) -> IndexExpr:
        tok = self._expect(TokenType.LBRACKET)
        idx = self._parse_expr()
        self._expect(TokenType.RBRACKET, "Expected ']' after index")
        return IndexExpr(object=obj, index=idx, line=tok.line, column=tok.column)

    def _parse_primary(self) -> Node:
        tok = self._peek()

        match tok.type:
            case TokenType.INT:
                self._advance()
                node = IntLiteral(value=tok.value, line=tok.line, column=tok.column)
                return node

            case TokenType.FLOAT:
                self._advance()
                node = FloatLiteral(value=tok.value, line=tok.line, column=tok.column)
                return node

            case TokenType.STRING:
                self._advance()
                return StringLiteral(value=tok.value, line=tok.line, column=tok.column)

            case TokenType.FSTRING:
                self._advance()
                return self._build_fstring_expr(tok)

            case TokenType.BOOL:
                self._advance()
                return BoolLiteral(value=tok.value, line=tok.line, column=tok.column)

            case TokenType.NULL:
                self._advance()
                return NullLiteral(line=tok.line, column=tok.column)

            case TokenType.IDENTIFIER:
                self._advance()
                ident = Identifier(name=tok.value, line=tok.line, column=tok.column)
                return ident

            case TokenType.AI:
                # 'ai' is a keyword for declarations, but can also be used as
                # an identifier (e.g. import ai, ai.isAvailable())
                self._advance()
                ident = Identifier(name=tok.value, line=tok.line, column=tok.column)
                return ident

            case TokenType.LBRACKET:
                return self._parse_list()

            case TokenType.LBRACE:
                return self._parse_map()

            case TokenType.LPAREN:
                return self._parse_grouped_or_tuple()


            case _:
                # Maybe a keyword used as expression (self, super)
                if tok.type == TokenType.SELF:
                    self._advance()
                    return Identifier(name="self", line=tok.line, column=tok.column)
                if tok.type == TokenType.SUPER:
                    self._advance()
                    return Identifier(name="super", line=tok.line, column=tok.column)
                raise TaipanSyntaxError(
                    f"Unexpected token '{tok.value}' ({tok.type.name})",
                    tok.line, tok.column
                )

    def _parse_range(self, start: Node) -> RangeExpr:
        tok = self._expect(TokenType.DOT_DOT)
        end = self._parse_addition()  # one precedence above range itself
        return RangeExpr(start=start, end=end, line=tok.line, column=tok.column)

    def _parse_list(self) -> ListLiteral:
        tok = self._expect(TokenType.LBRACKET)
        elements: List[Node] = []
        if not self._check(TokenType.RBRACKET):
            elements.append(self._parse_expr())
            while self._match(TokenType.COMMA):
                if self._check(TokenType.RBRACKET):
                    break
                elements.append(self._parse_expr())
        self._expect(TokenType.RBRACKET, "Expected ']' to close list")
        return ListLiteral(elements=elements, line=tok.line, column=tok.column)

    def _parse_map(self) -> MapLiteral:
        tok   = self._expect(TokenType.LBRACE)
        pairs = []
        if not self._check(TokenType.RBRACE):
            key = self._parse_expr()
            self._expect(TokenType.COLON, "Expected ':' after map key")
            val = self._parse_expr()
            pairs.append((key, val))
            while self._match(TokenType.COMMA):
                if self._check(TokenType.RBRACE):
                    break
                key = self._parse_expr()
                self._expect(TokenType.COLON, "Expected ':' after map key")
                val = self._parse_expr()
                pairs.append((key, val))
        self._expect(TokenType.RBRACE, "Expected '}' to close map")
        return MapLiteral(pairs=pairs, line=tok.line, column=tok.column)

    def _parse_grouped_or_tuple(self) -> Node:
        tok = self._expect(TokenType.LPAREN)
        # Empty parens: () => expr  is a zero-param lambda
        if self._check(TokenType.RPAREN):
            self._advance()
            if self._check(TokenType.FAT_ARROW):
                self._advance()
                body = self._parse_expr()
                return LambdaExpr(params=[], body=body, line=tok.line, column=tok.column)
            return TupleLiteral(elements=[], line=tok.line, column=tok.column)

        first = self._parse_expr()
        if self._match(TokenType.COMMA):
            elements = [first]
            if not self._check(TokenType.RPAREN):
                elements.append(self._parse_expr())
                while self._match(TokenType.COMMA):
                    if self._check(TokenType.RPAREN):
                        break
                    elements.append(self._parse_expr())
            self._expect(TokenType.RPAREN, "Expected ')' to close tuple")
            # Check for multi-param lambda: (x, y) => expr
            if self._check(TokenType.FAT_ARROW):
                self._advance()
                body   = self._parse_expr()
                params = self._exprs_to_params(elements, tok)
                return LambdaExpr(params=params, body=body, line=tok.line, column=tok.column)
            return TupleLiteral(elements=elements, line=tok.line, column=tok.column)

        self._expect(TokenType.RPAREN, "Expected ')' to close grouped expression")
        # Check for single-param lambda: (x) => expr
        if self._check(TokenType.FAT_ARROW):
            self._advance()
            body   = self._parse_expr()
            params = self._exprs_to_params([first], tok)
            return LambdaExpr(params=params, body=body, line=tok.line, column=tok.column)
        return first

    def _exprs_to_params(self, exprs: List[Node], tok: Token) -> List[Param]:
        """Convert a list of Identifier nodes to Param objects for a lambda."""
        params = []
        for expr in exprs:
            if not isinstance(expr, Identifier):
                raise TaipanSyntaxError(
                    "Lambda parameters must be identifiers", tok.line, tok.column
                )
            params.append(Param(name=expr.name, line=expr.line, column=expr.column))
        return params

    def _build_fstring_expr(self, tok: Token) -> Node:
        """Convert an FSTRING token's parts list into a chain of + BinaryExpr nodes.
        Each 'expr' part is re-lexed and re-parsed, then wrapped in str().
        """
        from taipan.compiler.lexer.lexer import Lexer as _Lexer

        parts = tok.value  # List of ('lit', str) or ('expr', str)
        if not parts:
            return StringLiteral(value="", line=tok.line, column=tok.column)

        nodes: List[Node] = []
        for kind, content in parts:
            if kind == "lit":
                nodes.append(StringLiteral(value=content, line=tok.line, column=tok.column))
            else:
                # Re-lex + re-parse the embedded expression
                sub_tokens = _Lexer(content, "<fstring>").tokenize()
                sub_ast    = Parser(sub_tokens, "<fstring>").parse()
                if sub_ast.body and isinstance(sub_ast.body[0], ExpressionStmt):
                    expr = sub_ast.body[0].expression
                else:
                    expr = NullLiteral(line=tok.line, column=tok.column)
                # Wrap in str() so concatenation always works
                wrapped = CallExpr(
                    callee=Identifier(name="str", line=tok.line, column=tok.column),
                    arguments=[expr],
                    line=tok.line, column=tok.column,
                )
                nodes.append(wrapped)

        # Chain parts with +
        result = nodes[0]
        for node in nodes[1:]:
            result = BinaryExpr(
                left=result, operator="+", right=node,
                line=tok.line, column=tok.column,
            )
        return result

    def _parse_type_annotation(self) -> TypeAnnotation:
        """Parse a structured type annotation: SimpleType or GenericType."""
        tok = self._expect(TokenType.IDENTIFIER, "Expected type name")
        name = tok.value
        
        if self._match(TokenType.LT):
            params = []
            while True:
                param = self._parse_type_annotation()
                params.append(param)
                if not self._match(TokenType.COMMA):
                    break
            self._expect(TokenType.GT, "Expected '>' to close type arguments")
            return GenericType(name=name, params=params, line=tok.line, column=tok.column)
            
        return SimpleType(name=name, line=tok.line, column=tok.column)
