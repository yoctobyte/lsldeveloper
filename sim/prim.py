import uuid
from typing import List, Dict, Any, Optional
from core.types import LSLVector, LSLRotation, NULL_KEY

class Prim:
    def __init__(self, name: str):
        self.name = name
        self.description = ""
        self.uuid = str(uuid.uuid4())
        self.local_pos = LSLVector()
        self.local_rot = LSLRotation()
        self.scale = LSLVector(0.5, 0.5, 0.5)
        self.floating_text = {"text": "", "color": LSLVector(1.0, 1.0, 1.0), "alpha": 1.0}
        self.particle_system = []
        self.texture_animation = None
        self.sound_state = {"mode": "stopped", "sound": "", "volume": 0.0}
        self.sound_history = []
        self.preloaded_sounds = set()
        self.parent_object: Optional['LSLObject'] = None
        self.link_number = 0
        self.inventory: List[InventoryItem] = []
        self.num_faces = 6

    def add_item(self, item: 'InventoryItem'):
        self.inventory.append(item)
        item.container_prim = self

    def __str__(self):
        return f"Prim('{self.name}', {self.uuid}, Link: {self.link_number})"

class InventoryItem:
    def __init__(self, name: str, item_type: int):
        self.name = name
        self.uuid = str(uuid.uuid4())
        self.type = item_type
        self.description = ""
        self.creator_key = "00000000-0000-0000-0000-000000000000"
        self.acquire_time = ""
        self.perm_mask = 0x7FFFFFFF
        self.container_prim: Optional[Prim] = None


class NotecardItem(InventoryItem):
    def __init__(self, name: str, text: str = ""):
        super().__init__(name, 7)
        self.text = text
        self.lines = text.splitlines()


class ObjectInventoryItem(InventoryItem):
    def __init__(self, name: str, template: dict):
        super().__init__(name, 6)
        self.template = template

    def rez(self, region, world, position, rotation, owner_key, creator_key):
        from harness.runtime import initialize_script
        from sim.object import LSLObject

        if world.rezzed_object_count >= world.max_rezzed_objects:
            return None

        obj = LSLObject(
            self.template.get("name", self.name),
            position,
            rotation,
            description=self.template.get("description", ""),
            owner_key=owner_key,
            creator_key=creator_key,
        )
        prim = Prim(f"{obj.name} Root")
        obj.add_prim(prim)
        region.add_object(obj)
        world.rezzed_object_count += 1

        for notecard in self.template.get("notecards", []):
            prim.add_item(NotecardItem(notecard.get("name", "Config"), notecard.get("text", "")))

        for script in self.template.get("scripts", []):
            item = ScriptItem(script.get("name", "script.lsl"), script.get("source", "default {}\n"))
            prim.add_item(item)
            initialize_script(item)

        return obj


class ScriptItem(InventoryItem):
    def __init__(self, name: str, source: str):
        super().__init__(name, 10)
        self.source = source
        self.running = False
        self.current_state = "default"
        self.event_queue = EventQueue()
        self.ctx = None # ExecutionContext
        self.ast = None # Script AST
        self.timer_interval = 0.0
        self.last_timer_fire = 0.0
        self.listeners: Dict[int, 'Listener'] = {}
        self.next_listener_handle = 1
        self.detected: List[Dict[str, Any]] = []
        self.sensor_repeat = None
        self.last_sensor_fire = 0.0

class Listener:
    def __init__(self, channel: int, name: str, key: str, message: str):
        self.channel = channel
        self.name = name # Filter by sender name
        self.key = key   # Filter by sender key
        self.message = message # Filter by message content

    def matches(self, channel: int, name: str, key: str, message: str) -> bool:
        if self.channel != channel: return False
        if self.name and self.name != name: return False
        if self.key and self.key != NULL_KEY and self.key != key: return False
        if self.message and self.message != message: return False
        return True

from events.queue import EventQueue
