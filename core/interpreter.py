from typing import Any, Dict, List
from .ast_nodes import *
from .builtins.runtime import UNHANDLED, call_builtin
from .lslconstants import default_globals
from .types import LSLVector, LSLRotation, LSLList, cast_to_lsl_type, NULL_KEY
from .exceptions import StateChangeException

class InterpreterError(Exception):
    pass

class ReturnException(Exception):
    def __init__(self, value: Any):
        self.value = value

class JumpException(Exception):
    def __init__(self, label: str):
        self.label = label

class ExecutionContext:
    def __init__(self, globals: Dict[str, Any] = None):
        self.globals = default_globals()
        if globals is not None:
            self.globals.update(globals)
        self.stack: List[Dict[str, Any]] = [] # For local variables

    def get_var(self, name: str) -> Any:
        for frame in reversed(self.stack):
            if name in frame:
                return frame[name]
        if name in self.globals:
            return self.globals[name]
        raise InterpreterError(f"Undefined variable: {name}")

    def set_var(self, name: str, value: Any):
        for frame in reversed(self.stack):
            if name in frame:
                frame[name] = value
                return
        if name in self.globals:
            self.globals[name] = value
            return
        raise InterpreterError(f"Cannot set undefined variable: {name}")

    def push_frame(self, frame: Dict[str, Any] = None):
        self.stack.append(frame if frame is not None else {})

    def pop_frame(self):
        self.stack.pop()

class Evaluator:
    def __init__(self, context: ExecutionContext, script: Any = None):
        self.ctx = context
        self.script = script # Reference to ScriptItem

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
        res = LSLList()
        for e in node.elements:
            val = self.evaluate(e)
            if isinstance(val, LSLList):
                res.extend(val)
            else:
                res.append(val)
        return res

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
        if node.op == '^': return left ^ right 
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

    def eval_AssignmentStmt(self, node: AssignmentStmt):
        # Allow assignment to be evaluated as an expression
        return self.exec_AssignmentStmt(node)

    def eval_FuncCallExpr(self, node: FuncCallExpr):
        args = [self.evaluate(a) for a in node.args]
        builtin_result = call_builtin(self, node.name, args)
        if builtin_result is not UNHANDLED:
            return builtin_result
        # User-defined functions
        if self.script and self.script.ast:
            func_def = next((g for g in self.script.ast.globals if isinstance(g, FunctionDef) and g.name == node.name), None)
            if func_def:
                # Push a new frame
                self.ctx.push_frame()
                try:
                    # Set parameters
                    for i, (p_type, p_name) in enumerate(func_def.parameters):
                        if i < len(args):
                            self.ctx.stack[-1][p_name] = args[i]
                    
                    # Execute body
                    try:
                        self.execute(func_def.body)
                    except ReturnException as e:
                        return e.value
                finally:
                    self.ctx.pop_frame()
                return None

        raise InterpreterError(f"Unknown function: {node.name}")

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
        if val is None:
            if node.type == 'integer': val = 0
            elif node.type == 'float': val = 0.0
            elif node.type == 'string': val = ""
            elif node.type == 'key': val = NULL_KEY
            elif node.type == 'vector': val = LSLVector()
            elif node.type == 'rotation': val = LSLRotation()
            elif node.type == 'list': val = LSLList()
        self.ctx.stack[-1][node.name] = val

    def exec_AssignmentStmt(self, node: AssignmentStmt):
        value = self.evaluate(node.value)
        if node.op == '=':
            pass
        else:
            current = self.evaluate(node.target)
            if node.op == '+=': value = current + value
            elif node.op == '-=': value = current - value
            elif node.op == '*=': value = current * value
            elif node.op == '/=': value = current / value
        
        if isinstance(node.target, VariableExpr):
            self.ctx.set_var(node.target.name, value)
        elif isinstance(node.target, ComponentAccess):
            container_val = self.evaluate(node.target.target)
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

    def exec_IfStmt(self, node: IfStmt):
        condition = self.evaluate(node.condition)
        if bool(condition):
            self.execute(node.then_branch)
        elif node.else_branch:
            self.execute(node.else_branch)

    def exec_WhileStmt(self, node: WhileStmt):
        while bool(self.evaluate(node.condition)):
            self.execute(node.body)

    def exec_DoWhileStmt(self, node: DoWhileStmt):
        while True:
            self.execute(node.body)
            if not bool(self.evaluate(node.condition)):
                break

    def exec_ForStmt(self, node: ForStmt):
        self.ctx.push_frame()
        for stmt in node.init:
            self.execute(stmt)
        while node.condition is None or bool(self.evaluate(node.condition)):
            self.execute(node.body)
            for expr in node.update:
                self.evaluate(expr)
        self.ctx.pop_frame()

    def exec_ReturnStmt(self, node: ReturnStmt):
        val = None
        if node.value:
            val = self.evaluate(node.value)
        raise ReturnException(val)

    def exec_JumpStmt(self, node: JumpStmt):
        raise JumpException(node.label)

    def exec_LabelStmt(self, node: LabelStmt):
        return None

    def exec_BlockStmt(self, node: BlockStmt):
        self.ctx.push_frame()
        try:
            i = 0
            while i < len(node.statements):
                try:
                    self.execute(node.statements[i])
                    i += 1
                except JumpException as e:
                    # Look for label in current block
                    label_idx = -1
                    for idx, stmt in enumerate(node.statements):
                        if isinstance(stmt, LabelStmt) and stmt.label == e.label:
                            label_idx = idx
                            break
                    if label_idx != -1:
                        i = label_idx
                        # Continue execution from the label (LSL skip logic)
                    else:
                        # Re-raise to parent block
                        raise e
        finally:
            self.ctx.pop_frame()

    def exec_StateChangeStmt(self, node: StateChangeStmt):
        raise StateChangeException(node.state_name)
