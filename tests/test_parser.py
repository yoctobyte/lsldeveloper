import sys
import os

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.lexer import Lexer
from core.parser import Parser

sample_lsl = """
// Sample LSL script for testing
integer gGlobalInt = 42;
string gGlobalStr = "Hello";
vector gVec = <1.0, 2.0, 3.0>;

float add(float a, float b) {
    return a + b;
}

default {
    state_entry() {
        llSay(0, "Started");
        llSetTimerEvent(1.0);
    }
    
    touch_start(integer num) {
        integer i;
        for (i = 0; i < num; i++) {
            llSay(0, "Touched by " + (string)num);
        }
        
        if (gGlobalInt > 0) {
            state other;
        }
    }
    
    timer() {
        gGlobalInt--;
        vector v = <1, 1, 1> + gVec;
        list l = ["item", 1, 2.0, <0,0,0>];
    }
}

state other {
    state_entry() {
        llSay(0, "In other state");
    }
}
"""

def test_parsing():
    lexer = Lexer(sample_lsl)
    tokens = lexer.tokenize()
    parser = Parser(tokens)

    ast = parser.parse()

    assert len(ast.globals) == 4
    assert [state.name for state in ast.states] == ["default", "other"]

if __name__ == "__main__":
    test_parsing()
