from typing import Any, Dict, List, Optional, Union
from .ast_nodes import *
from .types import LSLVector, LSLRotation, LSLList, cast_to_lsl_type

class InterpreterError(Exception):
    pass

class ExecutionContext:
    def __init__(self, globals: Dict[str, Any] = None):
        self.globals = globals if globals is not None else {}
        self.stack: List[Dict[str, Any]] = [] # For local variables

    def get_var(self, name: str) -> Any:
        # Check local stack first (top down)
        for frame in reversed(self.stack):
            if name in frame:
                return frame[name]
        # Check globals
        if name in self.globals:
            return self.globals[name]
        raise InterpreterError(f"Undefined variable: {name}")

    def set_var(self, name: str, value: Any):
        # Check local stack first
        for frame in reversed(self.stack):
            if name in frame:
                frame[name] = value
                return
        # Check globals
        if name in self.globals:
            self.globals[name] = value
            return
        raise InterpreterError(f"Cannot set undefined variable: {name}")

    def push_frame(self, frame: Dict[str, Any] = None):
        self.stack.append(frame if frame is not None else {})

    def pop_frame(self):
        self.stack.pop()

class Evaluator:
    def __init__(self, context: ExecutionContext):
        self.ctx = context

    def evaluate(self, node: Node) -> Any:
        method_name = f'eval_{type(node).__name__}'
        visitor = getattr(self, method_name, self.generic_eval)
        return visitor(node)

    def generic_eval(self, node: Node):
        raise InterpreterError(f"No evaluator for node type: {type(node).__name__}")

    def eval_IntegerLiteral(self, node: IntegerLiteral):
        return node.value

    def eval_FloatLiteral(self, node: FloatLiteral):
        return node.value

    def eval_StringLiteral(self, node: StringLiteral):
        return node.value

    def eval_VectorLiteral(self, node: VectorLiteral):
        return LSLVector(
            self.evaluate(node.x),
            self.evaluate(node.y),
            self.evaluate(node.z)
        )

    def eval_RotationLiteral(self, node: RotationLiteral):
        return LSLRotation(
            self.evaluate(node.x),
            self.evaluate(node.y),
            self.evaluate(node.z),
            self.evaluate(node.s)
        )

    def eval_ListLiteral(self, node: ListLiteral):
        return LSLList([self.evaluate(e) for e in node.elements])

    def eval_VariableExpr(self, node: VariableExpr):
        return self.ctx.get_var(node.name)

    def eval_ComponentAccess(self, node: ComponentAccess):
        target = self.evaluate(node.target)
        if isinstance(target, (LSLVector, LSLRotation)):
            if node.component == 'x': return target.x
            if node.component == 'y': return target.y
            if node.component == 'z': return target.z
            if node.component == 's' and isinstance(target, LSLRotation): return target.s
        raise InterpreterError(f"Invalid component access: {node.component} on {type(target).__name__}")

    def eval_BinOpExpr(self, node: BinOpExpr):
        left = self.evaluate(node.left)
        right = self.evaluate(node.right)
        
        if node.op == '+': return left + right
        if node.op == '-': return left - right
        if node.op == '*': return left * right
        if node.op == '/': return left / right
        if node.op == '%': return left % right
        if node.op == '&': return int(left) & int(right)
        if node.op == '|': return int(left) | int(right)
        if node.op == '^': return left ^ right # XOR or Cross Product
        if node.op == '&&': return int(bool(left) and bool(right))
        if node.op == '||': return int(bool(left) or bool(right))
        if node.op == '==': return int(left == right)
        if node.op == '!=': return int(left != right)
        if node.op == '<': return int(left < right)
        if node.op == '>': return int(left > right)
        if node.op == '<=': return int(left <= right)
        if node.op == '>=': return int(left >= right)
        if node.op == '<<': return int(left) << int(right)
        if node.op == '>>': return int(left) >> int(right)
        
        raise InterpreterError(f"Unsupported binary operator: {node.op}")

    def eval_UnaryOpExpr(self, node: UnaryOpExpr):
        right = self.evaluate(node.right)
        if node.op == '-': return -right
        if node.op == '!': return int(not bool(right))
        if node.op == '~': return ~int(right)
        # Prefix/Postfix ++ --
        if node.op == '++':
            val = right + 1
            if isinstance(node.right, VariableExpr):
                self.ctx.set_var(node.right.name, val)
            return val
        if node.op == '--':
            val = right - 1
            if isinstance(node.right, VariableExpr):
                self.ctx.set_var(node.right.name, val)
            return val
        raise InterpreterError(f"Unsupported unary operator: {node.op}")

    def eval_CastExpr(self, node: CastExpr):
        val = self.evaluate(node.expr)
        return cast_to_lsl_type(val, node.target_type)

    def execute(self, node: Stmt):
        method_name = f'exec_{type(node).__name__}'
        visitor = getattr(self, method_name, self.generic_exec)
        return visitor(node)

    def generic_exec(self, node: Stmt):
        raise InterpreterError(f"No executor for statement type: {type(node).__name__}")

    def exec_ExprStmt(self, node: ExprStmt):
        self.evaluate(node.expr)

    def exec_VarDeclStmt(self, node: VarDeclStmt):
        val = None
        if node.initial_value:
            val = self.evaluate(node.initial_value)
        # Initialize to LSL defaults if val is None
        if val is None:
            if node.type == 'integer': val = 0
            elif node.type == 'float': val = 0.0
            elif node.type == 'string': val = ""
            elif node.type == 'key': val = NULL_KEY
            elif node.type == 'vector': val = LSLVector()
            elif node.type == 'rotation': val = LSLRotation()
            elif node.type == 'list': val = LSLList()
        
        # Add to current frame
        self.ctx.stack[-1][node.name] = val

    def exec_AssignmentStmt(self, node: AssignmentStmt):
        value = self.evaluate(node.value)
        if node.op == '=':
            pass
        else:
            # Handle +=, -=, etc.
            current = self.evaluate(node.target)
            if node.op == '+=': value = current + value
            elif node.op == '-=': value = current - value
            elif node.op == '*=': value = current * value
            elif node.op == '/=': value = current / value
            # ... others ...
        
        if isinstance(node.target, VariableExpr):
            self.ctx.set_var(node.target.name, value)
        elif isinstance(node.target, ComponentAccess):
            # Complex: set component of vector/rotation
            # Needs to update the container
            container_val = self.evaluate(node.target.target)
            # Immutability check: LSL vectors are immutable in sense that you can't just change .x?
            # Actually you CAN: v.x = 1.0;
            # We need to recreate the object because our LSLVector is frozen
            new_val = container_val
            if isinstance(container_val, LSLVector):
                kwargs = {'x': container_val.x, 'y': container_val.y, 'z': container_val.z}
                kwargs[node.target.component] = float(value)
                new_val = LSLVector(**kwargs)
            elif isinstance(container_val, LSLRotation):
                kwargs = {'x': container_val.x, 'y': container_val.y, 'z': container_val.z, 's': container_val.s}
                kwargs[node.target.component] = float(value)
                new_val = LSLRotation(**kwargs)
            
            if isinstance(node.target.target, VariableExpr):
                self.ctx.set_var(node.target.target.name, new_val)
            else:
                raise InterpreterError("Complex component assignment not yet supported")
        return value

    def exec_BlockStmt(self, node: BlockStmt):
        self.ctx.push_frame()
        for stmt in node.statements:
            self.execute(stmt)
        self.ctx.pop_frame()

    # ... more statement executors (If, While, For) will be added in Phase 3 ...
