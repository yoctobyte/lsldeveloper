from typing import Dict, Optional
from .region import Region
from .console import Console
from .diagnostics import Diagnostic

class World:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(World, cls).__new__(cls)
            cls._instance.regions = {}
            cls._instance.console = Console()
            cls._instance.diagnostics = []
            cls._instance.latest_dialog = None
            cls._instance.max_rezzed_objects = 32
            cls._instance.rezzed_object_count = 0
        return cls._instance

    def add_region(self, region: Region):
        self.regions[region.uuid] = region
        region.world_console = self.console
        region.world = self

    def get_region(self, uuid: str) -> Optional[Region]:
        return self.regions.get(uuid)

    @property
    def default_region(self) -> Optional[Region]:
        return next(iter(self.regions.values()), None)

    def find_agent(self, agent_key: str):
        for region in self.regions.values():
            avatar = region.find_agent(agent_key)
            if avatar:
                return avatar
        return None

    def find_object(self, object_key: str):
        for region in self.regions.values():
            obj = region.find_object(object_key)
            if obj:
                return obj
        return None

    def entity_name(self, entity_key: str) -> str:
        avatar = self.find_agent(entity_key)
        if avatar:
            return avatar.name
        obj = self.find_object(entity_key)
        if obj:
            return obj.name
        return ""

    def reset(self):
        self.regions = {}
        self.console = Console()
        self.diagnostics = []
        self.latest_dialog = None
        self.max_rezzed_objects = 32
        self.rezzed_object_count = 0

    def add_diagnostic(self, diagnostic: Diagnostic):
        self.diagnostics.append(diagnostic)
        self.console.emit(
            diagnostic.severity,
            diagnostic.label(),
            source_name=diagnostic.object_name,
        )
