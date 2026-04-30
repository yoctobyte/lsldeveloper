import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional

class TokenType(Enum):
    # Keywords
    DEFAULT = auto()
    STATE = auto()
    IF = auto()
    ELSE = auto()
    FOR = auto()
    DO = auto()
    WHILE = auto()
    RETURN = auto()
    JUMP = auto()
    
    # Types
    T_INTEGER = auto()
    T_FLOAT = auto()
    T_STRING = auto()
    T_KEY = auto()
    T_VECTOR = auto()
    T_ROTATION = auto()
    T_LIST = auto()
    
    # Literals
    L_INTEGER = auto()
    L_FLOAT = auto()
    L_STRING = auto()
    
    # Identifiers
    IDENTIFIER = auto()
    
    # Operators and Punctuation
    LPAREN = auto()      # (
    RPAREN = auto()      # )
    LBRACE = auto()      # {
    RBRACE = auto()      # }
    LBRACKET = auto()    # [
    RBRACKET = auto()    # ]
    COMMA = auto()       # ,
    SEMICOLON = auto()   # ;
    DOT = auto()         # .
    AT = auto()          # @
    
    # Multi-char operators
    PLUS = auto()        # +
    MINUS = auto()       # -
    TIMES = auto()       # *
    DIVIDE = auto()      # /
    MOD = auto()         # %
    BIT_AND = auto()     # &
    BIT_OR = auto()      # |
    BIT_XOR = auto()     # ^
    BIT_NOT = auto()     # ~
    NOT = auto()         # !
    
    ASSIGN = auto()      # =
    PLUS_ASSIGN = auto() # +=
    MINUS_ASSIGN = auto()# -=
    TIMES_ASSIGN = auto()# *=
    DIVIDE_ASSIGN = auto()# /=
    MOD_ASSIGN = auto()  # %=
    AND_ASSIGN = auto()  # &=
    OR_ASSIGN = auto()   # |=
    XOR_ASSIGN = auto()  # ^=
    
    EQ = auto()          # ==
    NEQ = auto()         # !=
    LT = auto()          # <
    GT = auto()          # >
    LE = auto()          # <=
    GE = auto()          # >=
    
    AND = auto()         # &&
    OR = auto()          # ||
    
    LSHIFT = auto()      # <<
    RSHIFT = auto()      # >>
    LSHIFT_ASSIGN = auto()# <<=
    RSHIFT_ASSIGN = auto()# >>=
    
    INC = auto()         # ++
    DEC = auto()         # --
    
    EOF = auto()

@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    column: int

class Lexer:
    KEYWORDS = {
        'default': TokenType.DEFAULT,
        'state': TokenType.STATE,
        'if': TokenType.IF,
        'else': TokenType.ELSE,
        'for': TokenType.FOR,
        'do': TokenType.DO,
        'while': TokenType.WHILE,
        'return': TokenType.RETURN,
        'jump': TokenType.JUMP,
        
        'integer': TokenType.T_INTEGER,
        'float': TokenType.T_FLOAT,
        'string': TokenType.T_STRING,
        'key': TokenType.T_KEY,
        'vector': TokenType.T_VECTOR,
        'rotation': TokenType.T_ROTATION,
        'list': TokenType.T_LIST,
    }

    TOKEN_SPEC = [
        ('COMMENT_SINGLE', r'//.*'),
        ('COMMENT_MULTI', r'/\*[\s\S]*?\*/'),
        ('L_FLOAT',       r'\d*\.\d+([eE][+-]?\d+)?|\d+\.\d*([eE][+-]?\d+)?|\d+[eE][+-]?\d+'),
        ('L_INTEGER_HEX', r'0x[0-9a-fA-F]+'),
        ('L_INTEGER',     r'\d+'),
        ('L_STRING',      r'"([^"\\]|\\.)*"'),
        ('IDENTIFIER',    r'[a-zA-Z_][a-zA-Z0-9_]*'),
        
        ('LSHIFT_ASSIGN', r'<<='),
        ('RSHIFT_ASSIGN', r'>>='),
        ('LSHIFT',        r'<<'),
        ('RSHIFT',        r'>>'),
        
        ('PLUS_ASSIGN',   r'\+='),
        ('MINUS_ASSIGN',  r'-='),
        ('TIMES_ASSIGN',  r'\*='),
        ('DIVIDE_ASSIGN', r'/='),
        ('MOD_ASSIGN',    r'%='),
        ('AND_ASSIGN',    r'&='),
        ('OR_ASSIGN',     r'\|='),
        ('XOR_ASSIGN',    r'\^='),
        
        ('EQ',            r'=='),
        ('NEQ',           r'!='),
        ('LE',            r'<='),
        ('GE',            r'>='),
        ('AND',           r'&&'),
        ('OR',            r'\|\|'),
        ('INC',           r'\+\+'),
        ('DEC',           r'--'),
        
        ('LPAREN',        r'\('),
        ('RPAREN',        r'\)'),
        ('LBRACE',        r'\{'),
        ('RBRACE',        r'\}'),
        ('LBRACKET',      r'\['),
        ('RBRACKET',      r'\]'),
        ('COMMA',         r','),
        ('SEMICOLON',     r';'),
        ('DOT',           r'\.'),
        ('AT',            r'@'),
        
        ('PLUS',          r'\+'),
        ('MINUS',         r'-'),
        ('TIMES',         r'\*'),
        ('DIVIDE',        r'/'),
        ('MOD',           r'%'),
        ('BIT_AND',       r'&'),
        ('BIT_OR',        r'\|'),
        ('BIT_XOR',       r'\^'),
        ('BIT_NOT',       r'~'),
        ('NOT',           r'!'),
        ('ASSIGN',        r'='),
        ('LT',            r'<'),
        ('GT',            r'>'),
        
        ('NEWLINE',       r'\n'),
        ('SKIP',          r'[ \t\r]+'),
        ('MISMATCH',      r'.'),
    ]

    def __init__(self, source: str):
        self.source = source
        self.tokens = []
        self.regex = re.compile('|'.join('(?P<%s>%s)' % pair for pair in self.TOKEN_SPEC))

    def tokenize(self) -> List[Token]:
        line_num = 1
        line_start = 0
        for mo in self.regex.finditer(self.source):
            kind = mo.lastgroup
            value = mo.group()
            column = mo.start() - line_start + 1
            
            if kind == 'NEWLINE':
                line_start = mo.end()
                line_num += 1
                continue
            elif kind == 'SKIP' or kind == 'COMMENT_SINGLE' or kind == 'COMMENT_MULTI':
                if kind == 'COMMENT_MULTI':
                    line_num += value.count('\n')
                    # Update line_start if the comment has newlines
                    if '\n' in value:
                        line_start = mo.start() + value.rfind('\n') + 1
                continue
            elif kind == 'MISMATCH':
                raise SyntaxError(f'Unexpected character {value!r} at line {line_num}, column {column}')
            
            if kind == 'IDENTIFIER' and value in self.KEYWORDS:
                kind = self.KEYWORDS[value].name
                token_type = self.KEYWORDS[value]
            elif kind == 'L_INTEGER_HEX':
                # Convert hex to decimal string but keep it as L_INTEGER for AST
                # Handle LSL signed 32-bit wrap
                val = int(value, 16)
                if val > 0x7FFFFFFF:
                    val -= 0x100000000
                value = str(val)
                token_type = TokenType.L_INTEGER
            elif kind == 'L_STRING':
                # Strip quotes and handle escapes later in AST or here
                value = value[1:-1]
                token_type = TokenType.L_STRING
            else:
                token_type = TokenType[kind]
            
            self.tokens.append(Token(token_type, value, line_num, column))
            
        self.tokens.append(Token(TokenType.EOF, '', line_num, 0))
        return self.tokens
