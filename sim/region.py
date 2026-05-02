import uuid
from typing import Dict, List, Optional, Any
from core.types import LSLVector
from .object import LSLObject
from .avatar import Avatar
from .parcel import Parcel
from events.queue import LSLEvent

class Region:
    def __init__(
        self,
        name: str,
        handle: int = 0,
        *,
        corner: LSLVector = LSLVector(),
        estate_name: str = "Offline Estate",
    ):
        self.name = name
        self.handle = handle
        self.uuid = str(uuid.uuid4())
        self.corner = corner
        self.estate_name = estate_name
        self.time_dilation = 1.0
        self.fps = 45.0
        self.flags = 0
        self.wind = LSLVector(1.0, 0.0, 0.0)
        self.water_height = 20.0
        self.objects: Dict[str, LSLObject] = {}
        self.avatars: Dict[str, Avatar] = {}
        self.parcels: Dict[str, Parcel] = {}
        self.world = None

    def add_object(self, obj: LSLObject):
        self.objects[obj.uuid] = obj
        obj.region = self

    def add_avatar(self, avatar: Avatar):
        self.avatars[avatar.uuid] = avatar
        avatar.region = self

    def add_parcel(self, parcel: Parcel):
        self.parcels[parcel.uuid] = parcel

    @property
    def default_parcel(self) -> Optional[Parcel]:
        return next(iter(self.parcels.values()), None)

    def parcel_at(self, position: LSLVector) -> Optional[Parcel]:
        for parcel in self.parcels.values():
            if parcel.contains(position):
                return parcel
        return self.default_parcel

    def find_agent(self, agent_key: str) -> Optional[Avatar]:
        return self.avatars.get(agent_key)

    def find_object(self, object_key: str) -> Optional[LSLObject]:
        return self.objects.get(object_key)

    def entity_name(self, entity_key: str) -> str:
        avatar = self.find_agent(entity_key)
        if avatar:
            return avatar.name
        obj = self.find_object(entity_key)
        if obj:
            return obj.name
        return ""

    def broadcast_chat(self, sender_uuid: str, sender_name: str, channel: int, message: str):
        console = getattr(self, "world_console", None)
        if console:
            console.emit(
                "say",
                message,
                source_name=sender_name,
                source_key=sender_uuid,
                channel=channel,
                stdout_text=f"CHAT [Channel {channel}] {sender_name}: {message}",
            )
        else:
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
