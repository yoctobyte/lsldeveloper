import time
from typing import List
from sim.world import World
from sim.prim import ScriptItem
from events.queue import LSLEvent
from core.interpreter import Evaluator, ExecutionContext
from core.exceptions import StateChangeException
from core.builtins.runtime import queue_sensor_event
from sim.diagnostics import diagnostic_from_exception

class SimulationLoop:
    def __init__(self, world: World):
        self.world = world
        self.sim_time = 0.0
        self.tick_count = 0

    def tick(self, dt: float = 0.1):
        self.sim_time += dt
        self.tick_count += 1
        
        # 1. Update timers and sensors for all scripts
        for region in list(self.world.regions.values()):
            for obj in list(region.objects.values()):
                for prim in list(obj.prims):
                    for item in list(prim.inventory):
                        if isinstance(item, ScriptItem) and item.running:
                            self._process_script_tick(item, dt)

    def _process_script_tick(self, script: ScriptItem, dt: float):
        # Handle Timer
        if script.timer_interval > 0:
            if self.sim_time >= script.last_timer_fire + script.timer_interval:
                script.event_queue.push(LSLEvent("timer", []))
                script.last_timer_fire = self.sim_time

        if script.sensor_repeat:
            interval = script.sensor_repeat["interval"]
            if interval > 0 and self.sim_time >= script.last_sensor_fire + interval:
                queue_sensor_event(script, **script.sensor_repeat["query"])
                script.last_sensor_fire = self.sim_time

        # Process all events in the queue
        while not script.event_queue.empty():
            event = script.event_queue.pop()
            if event:
                self._execute_event(script, event)

    def _execute_event(self, script: ScriptItem, event: LSLEvent):
        handler = self._find_handler(script, script.current_state, event.name)
        if not handler:
            return

        handler._event_detected = event.detected
        try:
            self._run_handler(script, handler, event.args)
        except Exception as exc:
            script.running = False
            obj = script.container_prim.parent_object if script.container_prim else None
            region = obj.region if obj else self.world.default_region
            world = getattr(region, "world", self.world) if region else self.world
            world.add_diagnostic(
                diagnostic_from_exception(
                    exc,
                    phase=f"runtime:{event.name}",
                    object_name=obj.name if obj else "",
                    script_name=script.name,
                )
            )

    def _find_handler(self, script: ScriptItem, state_name: str, handler_name: str):
        state_def = next((s for s in script.ast.states if s.name == state_name), None)
        if not state_def:
            return None

        return next((h for h in state_def.handlers if h.name == handler_name), None)

    def _run_handler(self, script: ScriptItem, handler, args: list):
        evaluator = Evaluator(script.ctx, script)
        script.ctx.push_frame()
        previous_detected = script.detected
        script.detected = getattr(handler, "_event_detected", None) or script.detected
        for i, (type_name, param_name) in enumerate(handler.parameters):
            if i < len(args):
                script.ctx.stack[-1][param_name] = args[i]

        try:
            evaluator.execute(handler.body)
        except StateChangeException as e:
            self._transition_state(script, script.current_state, e.new_state)
        finally:
            script.detected = previous_detected
            script.ctx.pop_frame()

    def _transition_state(self, script: ScriptItem, old_state_name: str, new_state_name: str):
        state_exit = self._find_handler(script, old_state_name, "state_exit")
        if state_exit:
            self._run_handler(script, state_exit, [])

        script.current_state = new_state_name
        script.event_queue.clear()
        script.event_queue.push(LSLEvent("state_entry", []))
