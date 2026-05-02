import sys
import os

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.lexer import Lexer
from core.parser import Parser
from core.interpreter import Evaluator, ExecutionContext, GlobalVar
from sim.world import World
from sim.region import Region
from sim.object import LSLObject
from sim.prim import Prim, ScriptItem
from sim.avatar import Avatar
from events.loop import SimulationLoop, LSLEvent

sample_lsl = """
default {
    state_entry() {
        llListen(0, "", "", ""); // Listen on channel 0 for everything
        llSay(0, "Script is listening...");
    }
    
    listen(integer channel, string name, key id, string message) {
        if (message == "Hello") {
            llSay(0, "Hello " + name + "!");
        }
    }
}
"""

def test_avatar_chat(capsys):
    print("--- Setting up Simulator ---")
    world = World()
    region = Region("Test Region")
    world.add_region(region)
    
    obj = LSLObject("Listener Box")
    region.add_object(obj)
    prim = Prim("Root Prim")
    obj.add_prim(prim)
    
    avatar = Avatar("Test User")
    region.add_avatar(avatar)
    
    print("\n--- Loading Script ---")
    lexer = Lexer(sample_lsl)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    script_ast = parser.parse()
    
    script_item = ScriptItem("chat.lsl", sample_lsl)
    script_item.ast = script_ast
    script_item.running = True
    
    ctx = ExecutionContext()
    script_item.ctx = ctx
    prim.add_item(script_item)
    
    # Initialize state_entry
    script_item.event_queue.push(LSLEvent("state_entry", []))
    
    loop = SimulationLoop(world)
    
    print("\n--- Running Simulation ---")
    # Tick 0: state_entry executes, sets up llListen
    print("Tick 0: Executing state_entry...")
    loop.tick(0.1)
    
    # Avatar says Hello
    print("\nAvatar says 'Hello'...")
    avatar.say(0, "Hello")
    
    # Run for 5 more ticks to process queued events
    print("\nRunning 5 more ticks...")
    for i in range(5):
        print(f"Tick {i+1}...")
        loop.tick(0.1)
    
    print("\n--- Verification ---")
    assert "Hello Test User!" in capsys.readouterr().out

if __name__ == "__main__":
    test_avatar_chat()
