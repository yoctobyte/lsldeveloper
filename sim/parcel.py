import uuid
from dataclasses import dataclass, field
from typing import Dict

from core.types import LSLVector, NULL_KEY


@dataclass
class Parcel:
    name: str
    description: str = ""
    owner_key: str = NULL_KEY
    group_key: str = NULL_KEY
    area: int = 65536
    landing_point: LSLVector = field(default_factory=LSLVector)
    music_url: str = ""
    media_url: str = ""
    flags: int = 0
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict[str, str] = field(default_factory=dict)

    def contains(self, position: LSLVector) -> bool:
        # Single-parcel regions are enough for now. Later this can become bounds-based.
        return True
