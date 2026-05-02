from core.types import LSLVector
from sim.avatar import Avatar
from sim.object import LSLObject
from sim.parcel import Parcel
from sim.prim import Prim
from sim.region import Region
from sim.world import World


WORLD_PROFILES = {
    "none": 0,
    "one": 1,
    "couple": 2,
    "dozens": 24,
    "sixty_plus": 64,
}


def _avatar_position(index: int) -> LSLVector:
    if index == 0:
        return LSLVector(128.0, 128.0, 25.0)
    if index == 1:
        return LSLVector(132.0, 128.0, 25.0)
    ring = 4 + (index // 8) * 3
    offset = index % 8
    x_offsets = [ring, ring, 0, -ring, -ring, -ring, 0, ring]
    y_offsets = [0, ring, ring, ring, 0, -ring, -ring, -ring]
    return LSLVector(128.0 + x_offsets[offset], 128.0 + y_offsets[offset], 25.0)


def seed_demo_world(world: World, profile: str = "couple") -> dict:
    world.reset()

    region = Region(
        "Offline Sandbox",
        handle=1,
        corner=LSLVector(1000.0, 1000.0, 0.0),
        estate_name="Offline Estate",
    )
    world.add_region(region)

    avatar_count = WORLD_PROFILES.get(profile, WORLD_PROFILES["couple"])
    owner = None
    visitor = None
    avatars = []
    for index in range(avatar_count):
        if index == 0:
            avatar = Avatar("Offline Owner", _avatar_position(index), display_name="Offline Owner")
            owner = avatar
        elif index == 1:
            avatar = Avatar("External Visitor", _avatar_position(index), display_name="External Visitor")
            visitor = avatar
        else:
            avatar = Avatar(f"Demo Avatar {index:02d}", _avatar_position(index), display_name=f"Demo Avatar {index:02d}")
        region.add_avatar(avatar)
        avatars.append(avatar)

    if owner is None:
        owner = Avatar("Offline Owner", LSLVector(128.0, 128.0, 25.0), display_name="Offline Owner")
    if visitor is None:
        visitor = owner

    parcel = Parcel(
        "Offline Parcel",
        description="Default parcel for offline LSL tests",
        owner_key=owner.uuid,
        area=65536,
        landing_point=LSLVector(128.0, 128.0, 25.0),
        music_url="https://example.invalid/offline-stream",
        media_url="https://example.invalid/offline-media",
    )
    region.add_parcel(parcel)

    fixture = LSLObject(
        "Fixture Cube",
        LSLVector(130.0, 128.0, 25.0),
        owner_key=owner.uuid,
        creator_key=owner.uuid,
        description="Demo object available for object-detail queries",
    )
    fixture.add_prim(Prim("Fixture Root"))
    region.add_object(fixture)

    return {
        "region": region,
        "parcel": parcel,
        "owner": owner,
        "visitor": visitor,
        "avatars": avatars,
        "fixture": fixture,
    }
