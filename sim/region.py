import uuid
from typing import Dict, List, Optional, Any
from .object import LSLObject
from .avatar import Avatar
from events.queue import LSLEvent

class Region:
    def __init__(self, name: str, handle: int = 0):
        self.name = name
        self.handle = handle
        self.uuid = str(uuid.uuid4())
        self.objects: Dict[str, LSLObject] = {}
        self.avatars: Dict[str, Avatar] = {}

    def add_object(self, obj: LSLObject):
        self.objects[obj.uuid] = obj
        obj.region = self

    def add_avatar(self, avatar: Avatar):
        self.avatars[avatar.uuid] = avatar
        avatar.region = self

    def broadcast_chat(self, sender_uuid: str, sender_name: str, channel: int, message: str):
        print(f"CHAT [Channel {channel}] {sender_name}: {message}")
        # Route to all scripts in all objects in this region
        for obj in self.objects.values():
            for prim in obj.prims:
                for item in prim.inventory:
                    from .prim import ScriptItem
                    if isinstance(item, ScriptItem) and item.running:
                        # Check listeners
                        for handle, listener in item.listeners.items():
                            if listener.matches(channel, sender_name, sender_uuid, message):
                                item.event_queue.push(LSLEvent("listen", [channel, sender_name, sender_uuid, message]))

    def remove_object(self, obj_uuid: str):
        if obj_uuid in self.objects:
            del self.objects[obj_uuid]

    def __str__(self):
        return f"Region('{self.name}', {self.uuid})"
