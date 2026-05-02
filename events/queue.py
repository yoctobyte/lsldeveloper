from collections import deque
from dataclasses import dataclass
from typing import Any, List, Optional

@dataclass
class LSLEvent:
    name: str
    args: List[Any]
    detected: Optional[List[dict[str, Any]]] = None

class EventQueue:
    MAX_SIZE = 64

    def __init__(self):
        self.queue = deque()

    def push(self, event: LSLEvent):
        if len(self.queue) < self.MAX_SIZE:
            self.queue.append(event)
        else:
            # LSL drops events if queue is full
            pass

    def pop(self) -> Optional[LSLEvent]:
        if self.queue:
            return self.queue.popleft()
        return None

    def clear(self):
        self.queue.clear()

    def empty(self):
        return len(self.queue) == 0

    def __len__(self):
        return len(self.queue)
