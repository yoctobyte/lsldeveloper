from dataclasses import dataclass, field
from typing import List, Optional, Any, Union

@dataclass
class Node:
    pass

@dataclass
class Expr(Node):
    pass

@dataclass
class Stmt(Node):
    pass

@dataclass
class Literal(Expr):
    value: Any

@dataclass
class IntegerLiteral(Literal):
    value: int

@dataclass
class FloatLiteral(Literal):
    value: float

@dataclass
class StringLiteral(Literal):
    value: str

@dataclass
class VectorLiteral(Expr):
    x: Expr
    y: Expr
    z: Expr

@dataclass
class RotationLiteral(Expr):
    x: Expr
    y: Expr
    z: Expr
    s: Expr

@dataclass
class ListLiteral(Expr):
    elements: List[Expr]

@dataclass
class VariableExpr(Expr):
    name: str

@dataclass
class ComponentAccess(Expr):
    target: Expr
    component: str  # x, y, z, s

@dataclass
class BinOpExpr(Expr):
    left: Expr
    op: str
    right: Expr

@dataclass
class UnaryOpExpr(Expr):
    op: str
    right: Expr

@dataclass
class CastExpr(Expr):
    target_type: str
    expr: Expr

@dataclass
class FuncCallExpr(Expr):
    name: str
    args: List[Expr]

@dataclass
class BlockStmt(Stmt):
    statements: List[Stmt]

@dataclass
class VarDeclStmt(Stmt):
    type: str
    name: str
    initial_value: Optional[Expr] = None

@dataclass
class AssignmentStmt(Stmt):
    target: Union[VariableExpr, ComponentAccess]
    op: str  # =, +=, etc.
    value: Expr

@dataclass
class ExprStmt(Stmt):
    expr: Expr

@dataclass
class IfStmt(Stmt):
    condition: Expr
    then_branch: Stmt
    else_branch: Optional[Stmt] = None

@dataclass
class ForStmt(Stmt):
    init: List[Stmt]
    condition: Optional[Expr]
    update: List[Expr]
    body: Stmt

@dataclass
class WhileStmt(Stmt):
    condition: Expr
    body: Stmt

@dataclass
class DoWhileStmt(Stmt):
    body: Stmt
    condition: Expr

@dataclass
class ReturnStmt(Stmt):
    value: Optional[Expr] = None

@dataclass
class StateChangeStmt(Stmt):
    state_name: str

@dataclass
class JumpStmt(Stmt):
    label: str

@dataclass
class LabelStmt(Stmt):
    label: str

@dataclass
class EventHandler(Node):
    name: str
    parameters: List[tuple]  # (type, name)
    body: BlockStmt

@dataclass
class StateDef(Node):
    name: str
    handlers: List[EventHandler]

@dataclass
class GlobalVar(Node):
    type: str
    name: str
    initial_value: Optional[Expr] = None

@dataclass
class FunctionDef(Node):
    return_type: str
    name: str
    parameters: List[tuple]  # (type, name)
    body: BlockStmt

@dataclass
class Script(Node):
    globals: List[Union[GlobalVar, FunctionDef]]
    states: List[StateDef]
