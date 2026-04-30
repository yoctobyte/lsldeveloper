import uuid
from typing import List, Dict, Any, Optional
from core.types import LSLVector, LSLRotation

class Prim:
    def __init__(self, name: str):
        self.name = name
        self.uuid = str(uuid.uuid4())
        self.local_pos = LSLVector()
        self.local_rot = LSLRotation()
        self.parent_object: Optional['LSLObject'] = None
        self.link_number = 0
        self.inventory: List[InventoryItem] = []

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
        self.container_prim: Optional[Prim] = None

class ScriptItem(InventoryItem):
    def __init__(self, name: str, source: str):
        super().__init__(name, 10) # 10 is LSL script type
        self.source = source
        self.running = False
        self.context: Any = None # To be linked to Interpreter context
