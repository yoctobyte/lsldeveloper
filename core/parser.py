from typing import List, Optional, Union
from .lexer import Token, TokenType, Lexer
from .ast_nodes import *

class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self, offset: int = 0) -> Token:
        if self.pos + offset >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[self.pos + offset]

    def advance(self) -> Token:
        token = self.peek()
        if token.type != TokenType.EOF:
            self.pos += 1
        return token

    def check(self, type: TokenType) -> bool:
        return self.peek().type == type

    def match(self, *types: TokenType) -> bool:
        for type in types:
            if self.check(type):
                self.advance()
                return True
        return False

    def consume(self, type: TokenType, message: str) -> Token:
        if self.check(type):
            return self.advance()
        token = self.peek()
        raise SyntaxError(f"{message} at line {token.line}, column {token.column} (got {token.type.name})")

    def parse(self) -> Script:
        globals = []
        states = []
        
        while not self.check(TokenType.EOF):
            if self.check(TokenType.DEFAULT) or self.check(TokenType.STATE):
                states.append(self.parse_state())
            else:
                # Global variable or function
                # Format: type identifier ...
                # Or identifier ... (if it's a function with no return type? No, LSL functions must have type or return type? Actually LSL functions can be 'integer func()' or 'func()'. If no type, it's 'void' (not a keyword, just empty).
                
                type_name = ""
                if self.peek().type.name.startswith("T_"):
                    type_name = self.advance().value
                
                name = self.consume(TokenType.IDENTIFIER, "Expected identifier").value
                
                if self.check(TokenType.LPAREN):
                    # Function
                    globals.append(self.parse_function(type_name, name))
                else:
                    # Global variable
                    initial_value = None
                    if self.match(TokenType.ASSIGN):
                        initial_value = self.parse_expression()
                    self.consume(TokenType.SEMICOLON, "Expected ';' after global variable declaration")
                    globals.append(GlobalVar(type_name, name, initial_value))
                    
        return Script(globals, states)

    def parse_state(self) -> StateDef:
        name = "default"
        if self.match(TokenType.STATE):
            name = self.consume(TokenType.IDENTIFIER, "Expected state name").value
        else:
            self.consume(TokenType.DEFAULT, "Expected 'default' or 'state'")
            
        self.consume(TokenType.LBRACE, "Expected '{' at start of state")
        handlers = []
        while not self.check(TokenType.RBRACE) and not self.check(TokenType.EOF):
            handlers.append(self.parse_event_handler())
        self.consume(TokenType.RBRACE, "Expected '}' at end of state")
        return StateDef(name, handlers)

    def parse_event_handler(self) -> EventHandler:
        name = self.consume(TokenType.IDENTIFIER, "Expected event name").value
        self.consume(TokenType.LPAREN, "Expected '('")
        params = []
        if not self.check(TokenType.RPAREN):
            while True:
                type_name = self.consume_type()
                param_name = self.consume(TokenType.IDENTIFIER, "Expected parameter name").value
                params.append((type_name, param_name))
                if not self.match(TokenType.COMMA):
                    break
        self.consume(TokenType.RPAREN, "Expected ')'")
        body = self.parse_block()
        return EventHandler(name, params, body)

    def parse_function(self, return_type: str, name: str) -> FunctionDef:
        self.consume(TokenType.LPAREN, "Expected '('")
        params = []
        if not self.check(TokenType.RPAREN):
            while True:
                type_name = self.consume_type()
                param_name = self.consume(TokenType.IDENTIFIER, "Expected parameter name").value
                params.append((type_name, param_name))
                if not self.match(TokenType.COMMA):
                    break
        self.consume(TokenType.RPAREN, "Expected ')'")
        body = self.parse_block()
        return FunctionDef(return_type, name, params, body)

    def parse_block(self) -> BlockStmt:
        self.consume(TokenType.LBRACE, "Expected '{'")
        statements = []
        while not self.check(TokenType.RBRACE) and not self.check(TokenType.EOF):
            statements.append(self.parse_statement())
        self.consume(TokenType.RBRACE, "Expected '}'")
        return BlockStmt(statements)

    def parse_statement(self) -> Stmt:
        if self.check(TokenType.LBRACE):
            return self.parse_block()
        if self.match(TokenType.IF):
            return self.parse_if()
        if self.match(TokenType.FOR):
            return self.parse_for()
        if self.match(TokenType.WHILE):
            return self.parse_while()
        if self.match(TokenType.DO):
            return self.parse_do_while()
        if self.match(TokenType.RETURN):
            expr = None
            if not self.check(TokenType.SEMICOLON):
                expr = self.parse_expression()
            self.consume(TokenType.SEMICOLON, "Expected ';'")
            return ReturnStmt(expr)
        if self.match(TokenType.STATE):
            if self.check(TokenType.DEFAULT):
                self.advance()
                state_name = "default"
            else:
                state_name = self.consume(TokenType.IDENTIFIER, "Expected state name").value
            self.consume(TokenType.SEMICOLON, "Expected ';'")
            return StateChangeStmt(state_name)
        if self.match(TokenType.JUMP):
            label = self.consume(TokenType.IDENTIFIER, "Expected label name").value
            self.consume(TokenType.SEMICOLON, "Expected ';'")
            return JumpStmt(label)
        if self.match(TokenType.AT):
            label = self.consume(TokenType.IDENTIFIER, "Expected label name").value
            self.consume(TokenType.SEMICOLON, "Expected ';'")
            return LabelStmt(label)
            
        if self.match(TokenType.SEMICOLON):
            return BlockStmt([]) # Treat empty statement as empty block
            
        # Check for variable declaration: type identifier [= expr];
        if self.peek().type.name.startswith("T_"):
            type_name = self.advance().value
            name = self.consume(TokenType.IDENTIFIER, "Expected identifier").value
            initial_value = None
            if self.match(TokenType.ASSIGN):
                initial_value = self.parse_expression()
            self.consume(TokenType.SEMICOLON, "Expected ';'")
            return VarDeclStmt(type_name, name, initial_value)
            
        # Otherwise expression statement or assignment
        expr = self.parse_expression()
        
        # Assignment check
        if isinstance(expr, (VariableExpr, ComponentAccess)) and self.peek().type.name.endswith("_ASSIGN") or self.check(TokenType.ASSIGN):
            op_token = self.advance()
            value = self.parse_expression()
            self.consume(TokenType.SEMICOLON, "Expected ';'")
            return AssignmentStmt(expr, op_token.value, value)
            
        self.consume(TokenType.SEMICOLON, "Expected ';'")
        return ExprStmt(expr)

    def parse_if(self) -> IfStmt:
        self.consume(TokenType.LPAREN, "Expected '('")
        condition = self.parse_expression()
        self.consume(TokenType.RPAREN, "Expected ')'")
        then_branch = self.parse_statement()
        else_branch = None
        if self.match(TokenType.ELSE):
            else_branch = self.parse_statement()
        return IfStmt(condition, then_branch, else_branch)

    def parse_for(self) -> ForStmt:
        self.consume(TokenType.LPAREN, "Expected '('")
        init = []
        if not self.match(TokenType.SEMICOLON):
            while True:
                init.append(self.parse_statement_for_init()) # Special case for init list
                if not self.match(TokenType.COMMA):
                    break
            self.consume(TokenType.SEMICOLON, "Expected ';'")
            
        condition = None
        if not self.match(TokenType.SEMICOLON):
            condition = self.parse_expression()
            self.consume(TokenType.SEMICOLON, "Expected ';'")
            
        update = []
        if not self.check(TokenType.RPAREN):
            while True:
                update.append(self.parse_expression())
                if not self.match(TokenType.COMMA):
                    break
        self.consume(TokenType.RPAREN, "Expected ')'")
        body = self.parse_statement()
        return ForStmt(init, condition, update, body)

    def parse_statement_for_init(self) -> Stmt:
        # Special case for for-init: can be assignment or expression
        expr = self.parse_expression()
        if isinstance(expr, (VariableExpr, ComponentAccess)) and (self.peek().type.name.endswith("_ASSIGN") or self.check(TokenType.ASSIGN)):
            op_token = self.advance()
            value = self.parse_expression()
            return AssignmentStmt(expr, op_token.value, value)
        return ExprStmt(expr)

    def parse_while(self) -> WhileStmt:
        self.consume(TokenType.LPAREN, "Expected '('")
        condition = self.parse_expression()
        self.consume(TokenType.RPAREN, "Expected ')'")
        body = self.parse_statement()
        return WhileStmt(condition, body)

    def parse_do_while(self) -> DoWhileStmt:
        body = self.parse_statement()
        self.consume(TokenType.WHILE, "Expected 'while'")
        self.consume(TokenType.LPAREN, "Expected '('")
        condition = self.parse_expression()
        self.consume(TokenType.RPAREN, "Expected ')'")
        self.consume(TokenType.SEMICOLON, "Expected ';'")
        return DoWhileStmt(body, condition)

    def parse_expression(self) -> Expr:
        return self.parse_assignment()

    def parse_assignment(self) -> Expr:
        # This is tricky because we need to know if the left side is a valid target
        # For simplicity, we parse a logical or and then check if it's followed by an assignment operator
        expr = self.parse_logical_or()
        
        if self.match(TokenType.ASSIGN, TokenType.PLUS_ASSIGN, TokenType.MINUS_ASSIGN, 
                      TokenType.TIMES_ASSIGN, TokenType.DIVIDE_ASSIGN, TokenType.MOD_ASSIGN,
                      TokenType.AND_ASSIGN, TokenType.OR_ASSIGN, TokenType.XOR_ASSIGN,
                      TokenType.LSHIFT_ASSIGN, TokenType.RSHIFT_ASSIGN):
            op = self.tokens[self.pos-1].value
            value = self.parse_assignment()
            if isinstance(expr, (VariableExpr, ComponentAccess)):
                # This return type is technically an assignment EXPRESSION in some languages, 
                # but LSL doesn't really allow assignment as expression except in 'for'?
                # Actually LSL DOES NOT allow assignment as expression: `if(a=b)` is illegal.
                # So we should probably handle this in parse_statement.
                # But wait, `for(a=0; ...)` uses it.
                # Let's keep it as a special node.
                return AssignmentStmt(expr, op, value) 
            raise SyntaxError("Invalid assignment target")
        return expr

    def parse_logical_or(self) -> Expr:
        expr = self.parse_logical_and()
        while self.match(TokenType.OR):
            op = self.tokens[self.pos-1].value
            right = self.parse_logical_and()
            expr = BinOpExpr(expr, op, right)
        return expr

    def parse_logical_and(self) -> Expr:
        expr = self.parse_bitwise_or()
        while self.match(TokenType.AND):
            op = self.tokens[self.pos-1].value
            right = self.parse_bitwise_or()
            expr = BinOpExpr(expr, op, right)
        return expr

    def parse_bitwise_or(self) -> Expr:
        expr = self.parse_bitwise_xor()
        while self.match(TokenType.BIT_OR):
            op = self.tokens[self.pos-1].value
            right = self.parse_bitwise_xor()
            expr = BinOpExpr(expr, op, right)
        return expr

    def parse_bitwise_xor(self) -> Expr:
        expr = self.parse_bitwise_and()
        while self.match(TokenType.BIT_XOR):
            op = self.tokens[self.pos-1].value
            right = self.parse_bitwise_and()
            expr = BinOpExpr(expr, op, right)
        return expr

    def parse_bitwise_and(self) -> Expr:
        expr = self.parse_equality()
        while self.match(TokenType.BIT_AND):
            op = self.tokens[self.pos-1].value
            right = self.parse_equality()
            expr = BinOpExpr(expr, op, right)
        return expr

    def parse_equality(self) -> Expr:
        expr = self.parse_comparison()
        while self.match(TokenType.EQ, TokenType.NEQ):
            op = self.tokens[self.pos-1].value
            right = self.parse_comparison()
            expr = BinOpExpr(expr, op, right)
        return expr

    def parse_comparison(self) -> Expr:
        expr = self.parse_shift()
        while self.match(TokenType.LT, TokenType.GT, TokenType.LE, TokenType.GE):
            op = self.tokens[self.pos-1].value
            right = self.parse_shift()
            expr = BinOpExpr(expr, op, right)
        return expr

    def parse_shift(self) -> Expr:
        expr = self.parse_term()
        while self.match(TokenType.LSHIFT, TokenType.RSHIFT):
            op = self.tokens[self.pos-1].value
            right = self.parse_term()
            expr = BinOpExpr(expr, op, right)
        return expr

    def parse_term(self) -> Expr:
        expr = self.parse_factor()
        while self.match(TokenType.PLUS, TokenType.MINUS):
            op = self.tokens[self.pos-1].value
            right = self.parse_factor()
            expr = BinOpExpr(expr, op, right)
        return expr

    def parse_factor(self) -> Expr:
        expr = self.parse_unary()
        while self.match(TokenType.TIMES, TokenType.DIVIDE, TokenType.MOD):
            op = self.tokens[self.pos-1].value
            right = self.parse_unary()
            expr = BinOpExpr(expr, op, right)
        return expr

    def parse_unary(self) -> Expr:
        if self.match(TokenType.NOT, TokenType.BIT_NOT, TokenType.MINUS, TokenType.INC, TokenType.DEC):
            op = self.tokens[self.pos-1].value
            right = self.parse_unary()
            return UnaryOpExpr(op, right)
            
        # Check for type cast: (type)expr
        if self.check(TokenType.LPAREN):
            # Lookahead: ( type ) ...
            if self.peek(1).type.name.startswith("T_") and self.peek(2).type == TokenType.RPAREN:
                # Potential cast. Check if next token is NOT an operator.
                # Actually in LSL, (type) is always a cast if it fits.
                # But we should be careful with (integer)(a+b)
                self.advance() # (
                target_type = self.advance().value
                self.advance() # )
                expr = self.parse_unary()
                return CastExpr(target_type, expr)
                
        return self.parse_postfix()

    def parse_postfix(self) -> Expr:
        expr = self.parse_primary()
        while True:
            if self.match(TokenType.INC, TokenType.DEC):
                op = self.tokens[self.pos-1].value
                expr = UnaryOpExpr(op, expr) # Postfix unary
            elif self.match(TokenType.DOT):
                component = self.consume(TokenType.IDENTIFIER, "Expected component name (x, y, z, or s)").value
                expr = ComponentAccess(expr, component)
            else:
                break
        return expr

    def parse_primary(self) -> Expr:
        if self.match(TokenType.L_INTEGER):
            return IntegerLiteral(int(self.tokens[self.pos-1].value))
        if self.match(TokenType.L_FLOAT):
            return FloatLiteral(float(self.tokens[self.pos-1].value))
        if self.match(TokenType.L_STRING):
            return StringLiteral(self.tokens[self.pos-1].value)
            
        # Ambiguity: < expr, expr, expr > (vector) vs < (comparison)
        if self.check(TokenType.LT):
            # Lookahead to see if it's a vector or rotation literal
            # We look for commas and closing >
            vector_expr = self.try_parse_vector_or_rotation()
            if vector_expr:
                return vector_expr
            # If not a vector, it's just a comparison, but parse_comparison should handle it.
            # Wait, if we are in parse_primary, we shouldn't have hit a comparison LT.
            # LT should have been handled by parse_comparison.
            # If we are here, it's likely a vector.
            
        if self.match(TokenType.LBRACKET):
            elements = []
            if not self.check(TokenType.RBRACKET):
                while True:
                    elements.append(self.parse_expression())
                    if not self.match(TokenType.COMMA):
                        break
            self.consume(TokenType.RBRACKET, "Expected ']'")
            return ListLiteral(elements)
            
        if self.match(TokenType.IDENTIFIER):
            name = self.tokens[self.pos-1].value
            if self.match(TokenType.LPAREN):
                args = []
                if not self.check(TokenType.RPAREN):
                    while True:
                        args.append(self.parse_expression())
                        if not self.match(TokenType.COMMA):
                            break
                self.consume(TokenType.RPAREN, "Expected ')'")
                return FuncCallExpr(name, args)
            return VariableExpr(name)
            
        if self.match(TokenType.LPAREN):
            expr = self.parse_expression()
            self.consume(TokenType.RPAREN, "Expected ')'")
            return expr
            
        token = self.peek()
        raise SyntaxError(f"Expected expression at line {token.line}, column {token.column} (got {token.type.name})")

    def try_parse_vector_or_rotation(self) -> Optional[Expr]:
        # Save state
        saved_pos = self.pos
        try:
            self.advance() # <
            x = self.parse_shift()
            self.consume(TokenType.COMMA, "Expected ','")
            y = self.parse_shift()
            self.consume(TokenType.COMMA, "Expected ','")
            z = self.parse_shift()
            
            if self.match(TokenType.COMMA):
                s = self.parse_shift()
                self.consume(TokenType.GT, "Expected '>'")
                return RotationLiteral(x, y, z, s)
            
            self.consume(TokenType.GT, "Expected '>'")
            return VectorLiteral(x, y, z)
        except SyntaxError:
            self.pos = saved_pos
            return None

    def consume_type(self) -> str:
        token = self.advance()
        if not token.type.name.startswith("T_"):
            raise SyntaxError(f"Expected type name at line {token.line}, column {token.column}")
        return token.value
