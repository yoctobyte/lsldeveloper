import time
from typing import List
from sim.world import World
from sim.prim import ScriptItem
from events.queue import LSLEvent
from core.interpreter import Evaluator, ExecutionContext
from core.exceptions import StateChangeException

class SimulationLoop:
    def __init__(self, world: World):
        self.world = world
        self.sim_time = 0.0
        self.tick_count = 0

    def tick(self, dt: float = 0.1):
        self.sim_time += dt
        self.tick_count += 1
        
        # 1. Update timers and sensors for all scripts
        for region in self.world.regions.values():
            for obj in region.objects.values():
                for prim in obj.prims:
                    for item in prim.inventory:
                        if isinstance(item, ScriptItem) and item.running:
                            self._process_script_tick(item, dt)

    def _process_script_tick(self, script: ScriptItem, dt: float):
        # Handle Timer
        if script.timer_interval > 0:
            if self.sim_time >= script.last_timer_fire + script.timer_interval:
                print(f"DEBUG: Timer firing for {script.name} at T={self.sim_time}")
                script.event_queue.push(LSLEvent("timer", []))
                script.last_timer_fire = self.sim_time

        # Process one event from the queue
        event = script.event_queue.pop()
        if event:
            print(f"DEBUG: Executing event {event.name} for {script.name}")
            self._execute_event(script, event)

    def _execute_event(self, script: ScriptItem, event: LSLEvent):
        # Find the handler in the current state
        state_def = next((s for s in script.ast.states if s.name == script.current_state), None)
        if not state_def:
            return

        handler = next((h for h in state_def.handlers if h.name == event.name), None)
        if not handler:
            return

        # Execute the handler
        evaluator = Evaluator(script.ctx, script)
        
        # Setup parameters
        # For now, we don't have many events with parameters
        # But we'd push a frame and set them here
        script.ctx.push_frame()
        for i, (type_name, param_name) in enumerate(handler.parameters):
            if i < len(event.args):
                script.ctx.stack[-1][param_name] = event.args[i]
        
        try:
            evaluator.execute(handler.body)
        except StateChangeException as e:
            # Handle state transition
            self._transition_state(script, script.current_state, e.new_state)
        finally:
            script.ctx.pop_frame()

    def _transition_state(self, script: ScriptItem, old_state_name: str, new_state_name: str):
        # 1. Fire state_exit of old state (if exists)
        # TODO: Implement state_exit
        
        # 2. Update state
        script.current_state = new_state_name
        
        # 3. Clear event queue (except for some special events, but LSL standard is clear)
        script.event_queue.clear()
        
        # 4. Fire state_entry of new state
        script.event_queue.push(LSLEvent("state_entry", []))
