import uuid
from typing import List, Optional, Dict
from core.types import LSLVector, LSLRotation, NULL_KEY

class LSLObject:
    def __init__(
        self,
        name: str,
        position: LSLVector = LSLVector(),
        rotation: LSLRotation = LSLRotation(),
        *,
        description: str = "",
        owner_key: str = NULL_KEY,
        creator_key: str = NULL_KEY,
        group_key: str = NULL_KEY,
    ):
        self.name = name
        self.uuid = str(uuid.uuid4())
        self.description = description
        self.position = position
        self.rotation = rotation
        self.velocity = LSLVector()
        self.angular_velocity = LSLVector()
        self.prims: List['Prim'] = []
        self.region: Optional['Region'] = None
        self.owner_key = owner_key
        self.creator_key = creator_key
        self.group_key = group_key
        self.linkset_data: Dict[str, str] = {} # Key-value store for llLinksetData
        self.metadata: Dict[str, str] = {}

    @property
    def root_prim(self) -> Optional['Prim']:
        return self.prims[0] if self.prims else None

    def add_prim(self, prim: 'Prim'):
        self.prims.append(prim)
        prim.parent_object = self
        # Link numbers: root is 1, child is 2...
        prim.link_number = len(self.prims)

    def dispatch_event(self, event_name: str, args: list, link_num: int = 0):
        from events.queue import LSLEvent
        from .prim import ScriptItem

        for prim in self.prims:
            if link_num and prim.link_number != link_num:
                continue
            for item in prim.inventory:
                if isinstance(item, ScriptItem) and item.running:
                    item.event_queue.push(LSLEvent(event_name, args))

    def __str__(self):
        return f"Object('{self.name}', {self.uuid}, Prims: {len(self.prims)})"
