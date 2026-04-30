import sys
import os

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.lexer import Lexer
from core.parser import Parser
from core.ast_nodes import GlobalVar
from core.interpreter import Evaluator, ExecutionContext
from sim.world import World
from sim.region import Region
from sim.object import LSLObject
from sim.prim import Prim, ScriptItem

sample_lsl = """
integer gInt = 10 + 32;
float gFloat = 1.5 * 2.0;
vector gVec = <1.0, 2.0, 3.0> + <0.5, 0.5, 0.5>;
rotation gRot = <0,0,0,1>;
list gList = ["A", 1, 2.0] + [gInt, gVec];
string gStr = (string)gVec;
"""

def test_sim_baseline():
    print("--- Setting up Simulator ---")
    world = World()
    region = Region("Test Region")
    world.add_region(region)
    
    obj = LSLObject("Test Object")
    region.add_object(obj)
    
    prim = Prim("Root Prim")
    obj.add_prim(prim)
    
    print(f"Created {world}")
    print(f"Created {region}")
    print(f"Created {obj}")
    print(f"Created {prim}")
    
    print("\n--- Parsing Script ---")
    lexer = Lexer(sample_lsl)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    script_ast = parser.parse()
    
    print("\n--- Initializing Global State ---")
    # In LSL, globals are initialized before state_entry
    ctx = ExecutionContext()
    evaluator = Evaluator(ctx)
    
    for item in script_ast.globals:
        if isinstance(item, GlobalVar):
            val = None
            if item.initial_value:
                val = evaluator.evaluate(item.initial_value)
            ctx.globals[item.name] = val
            print(f"Global {item.name} = {val} ({type(val).__name__})")

    print("\n--- Verification ---")
    assert ctx.globals['gInt'] == 42
    assert ctx.globals['gFloat'] == 3.0
    print("All assertions passed!")

if __name__ == "__main__":
    test_sim_baseline()
