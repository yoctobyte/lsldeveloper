from typing import Dict, Optional
from .region import Region

class World:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(World, cls).__new__(cls)
            cls._instance.regions = {}
        return cls._instance

    def add_region(self, region: Region):
        self.regions[region.uuid] = region

    def get_region(self, uuid: str) -> Optional[Region]:
        return self.regions.get(uuid)

    def reset(self):
        self.regions = {}
