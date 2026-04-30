import uuid
from typing import Dict, List, Optional
from core.types import LSLVector
from .object import LSLObject

class Region:
    def __init__(self, name: str, handle: int = 0):
        self.name = name
        self.handle = handle
        self.uuid = str(uuid.uuid4())
        self.objects: Dict[str, LSLObject] = {}
        self.avatars: Dict[str, Any] = {} # Avatar class to be implemented

    def add_object(self, obj: LSLObject):
        self.objects[obj.uuid] = obj
        obj.region = self

    def remove_object(self, obj_uuid: str):
        if obj_uuid in self.objects:
            del self.objects[obj_uuid]

    def __str__(self):
        return f"Region('{self.name}', {self.uuid})"
