import uuid
from core.types import LSLVector, LSLRotation, NULL_KEY

class Avatar:
    def __init__(
        self,
        name: str,
        position: LSLVector = LSLVector(),
        *,
        display_name: str = "",
        group_key: str = NULL_KEY,
        language: str = "en",
    ):
        self.name = name
        self.display_name = display_name or name
        self.uuid = str(uuid.uuid4())
        self.position = position
        self.rotation = LSLRotation()
        self.group_key = group_key
        self.language = language
        self.is_online = True
        self.region = None

    def say(self, channel: int, message: str):
        if self.region:
            self.region.broadcast_chat(self.uuid, self.name, channel, message)

    def touch(self, object_uuid: str, link_num: int = 0):
        if self.region:
            obj = self.region.objects.get(object_uuid)
            if obj:
                obj.dispatch_event("touch_start", [1]) # num_detected

    def __str__(self):
        return f"Avatar('{self.name}', {self.uuid})"
