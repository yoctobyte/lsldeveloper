import sys
import os
import time

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.lexer import Lexer
from core.parser import Parser
from core.interpreter import Evaluator, ExecutionContext, GlobalVar
from sim.world import World
from sim.region import Region
from sim.object import LSLObject
from sim.prim import Prim, ScriptItem
from events.loop import SimulationLoop, LSLEvent

sample_lsl = """
default {
    state_entry() {
        llSay(0, "Default state started");
        llSetTimerEvent(0.5);
    }
    
    timer() {
        llSay(0, "Timer fired, switching state");
        state other;
    }
}

state other {
    state_entry() {
        llSay(0, "In other state");
        llSetTimerEvent(0.0); // Stop timer
    }
}
"""

def test_state_machine():
    print("--- Setting up Simulator ---")
    world = World()
    region = Region("Test Region")
    world.add_region(region)
    obj = LSLObject("Test Object")
    region.add_object(obj)
    prim = Prim("Root Prim")
    obj.add_prim(prim)
    
    print("\n--- Loading Script ---")
    lexer = Lexer(sample_lsl)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    script_ast = parser.parse()
    
    script_item = ScriptItem("statetest.lsl", sample_lsl)
    script_item.ast = script_ast
    script_item.running = True
    
    # Initialize globals
    ctx = ExecutionContext()
    evaluator = Evaluator(ctx, script_item)
    for item in script_ast.globals:
        if isinstance(item, GlobalVar):
            val = evaluator.evaluate(item.initial_value) if item.initial_value else None
            ctx.globals[item.name] = val
    
    script_item.ctx = ctx
    prim.add_item(script_item)
    
    # Manually fire initial state_entry
    script_item.event_queue.push(LSLEvent("state_entry", []))
    
    print("\n--- Starting Simulation Loop ---")
    loop = SimulationLoop(world)
    
    # Run for 15 ticks (1.5 seconds simulated time)
    for i in range(15):
        print(f"\nTick {i} (T={loop.sim_time:.1f})")
        loop.tick(0.1)
        if script_item.current_state == "other" and i > 6:
            # Wait a bit to see the state_entry of 'other'
            pass

    print("\n--- Verification ---")
    assert script_item.current_state == "other"
    print("State transition verified!")

if __name__ == "__main__":
    test_state_machine()
