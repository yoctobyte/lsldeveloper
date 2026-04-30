import uuid
from typing import List, Optional
from core.types import LSLVector, LSLRotation

class LSLObject:
    def __init__(self, name: str, position: LSLVector = LSLVector(), rotation: LSLRotation = LSLRotation()):
        self.name = name
        self.uuid = str(uuid.uuid4())
        self.position = position
        self.rotation = rotation
        self.prims: List['Prim'] = []
        self.region: Optional['Region'] = None
        self.owner_key = NULL_KEY # Should import NULL_KEY from types

    @property
    def root_prim(self) -> Optional['Prim']:
        return self.prims[0] if self.prims else None

    def add_prim(self, prim: 'Prim'):
        self.prims.append(prim)
        prim.parent_object = self
        # Link numbers: root is 1, child is 2...
        prim.link_number = len(self.prims)

    def __str__(self):
        return f"Object('{self.name}', {self.uuid}, Prims: {len(self.prims)})"

from core.types import NULL_KEY
