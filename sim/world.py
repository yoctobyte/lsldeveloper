import uuid
from typing import Dict, Optional, Tuple, Any
from .region import Region
from .console import Console
from .diagnostics import Diagnostic

# Synthetic URL prefix for intra-sim HTTP routing
SIM_URL_PREFIX = "http://sim.local/"

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
            # Intra-sim HTTP routing
            cls._instance.url_registry: Dict[str, Any] = {}        # url → ScriptItem
            cls._instance.pending_http: Dict[str, Tuple] = {}      # serve_key → (caller_script, caller_key)
        return cls._instance

    # ── Intra-sim URL management ──────────────────────────────────────────
    def register_url(self, script) -> str:
        url = SIM_URL_PREFIX + uuid.uuid4().hex[:12]
        self.url_registry[url] = script
        return url

    def release_url(self, url: str):
        self.url_registry.pop(url, None)

    def is_sim_url(self, url: str) -> bool:
        return url.startswith(SIM_URL_PREFIX)

    def resolve_url(self, url: str):
        return self.url_registry.get(url)

    def register_pending_http(self, serve_key: str, caller_script, caller_key: str):
        self.pending_http[serve_key] = (caller_script, caller_key)

    def resolve_pending_http(self, serve_key: str):
        return self.pending_http.pop(serve_key, None)

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
        self.url_registry = {}
        self.pending_http = {}

    def add_diagnostic(self, diagnostic: Diagnostic):
        self.diagnostics.append(diagnostic)
        self.console.emit(
            diagnostic.severity,
            diagnostic.label(),
            source_name=diagnostic.object_name,
        )
