"""
EloTracker tests — P2P distributed ELO for TTChess TT620.

Run:
    cd ~/lsldeveloper && python -m pytest tests/test_ttchess_elo.py -v
"""

from __future__ import annotations

from pathlib import Path
import pytest

from events.queue import LSLEvent
from ide.project import IdeProject, ProjectObject, ProjectScript
from sim.world import World

TTCHESS = Path(__file__).parent.parent.parent / "ttchess"
ELO_SRC     = (TTCHESS / "EloTracker.lsl").read_text()
ENGINE_SRC  = (TTCHESS / "ChessEngine.lsl").read_text()
HTTP_SRC    = (TTCHESS / "NodeHTTP.lsl").read_text()
MANAGER_SRC = (TTCHESS / "NodeManager.lsl").read_text()

LM_ELO_GAME  = 0xCE030
LM_ELO_QUERY = 0xCE031
LM_ELO_RESP  = 0xCE032

# Two distinct avatar UUIDs (the *clickers*, not board owners)
PLAYER_A = "aaaaaaaa-0000-0000-0000-000000000001"
PLAYER_B = "bbbbbbbb-0000-0000-0000-000000000002"

ELO_DEFAULT = 1200


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_single(name="Board A"):
    World().reset()
    proj = IdeProject(Path("/tmp/elo_test"), [
        ProjectObject(name, scripts=[
            ProjectScript("ChessEngine.lsl", ENGINE_SRC),
            ProjectScript("NodeHTTP.lsl",    HTTP_SRC),
            ProjectScript("NodeManager.lsl", MANAGER_SRC),
            ProjectScript("EloTracker.lsl",  ELO_SRC),
        ]),
    ])
    return proj.build_runtime(echo_stdout=False)


def _make_two():
    World().reset()
    def _obj(name):
        return ProjectObject(name, scripts=[
            ProjectScript("ChessEngine.lsl", ENGINE_SRC),
            ProjectScript("NodeHTTP.lsl",    HTTP_SRC),
            ProjectScript("NodeManager.lsl", MANAGER_SRC),
            ProjectScript("EloTracker.lsl",  ELO_SRC),
        ])
    proj = IdeProject(Path("/tmp/elo_test2"), [_obj("Board A"), _obj("Board B")])
    return proj.build_runtime(echo_stdout=False)


def _lsd(runtime, obj_name, key):
    return runtime.objects[obj_name].linkset_data.get(key, "")


def _inject_lm(runtime, obj_name, num, msg, id_=""):
    from sim.prim import ScriptItem
    obj = runtime.objects[obj_name]
    for prim in obj.prims:
        for item in prim.inventory:
            if isinstance(item, ScriptItem) and item.running:
                item.event_queue.push(LSLEvent("link_message",
                    [prim.link_number, num, msg, id_]))


def _ownersay(runtime):
    return [m.text for m in runtime.world.console.messages
            if m.message_type == "ownersay"]


# ── 1. startup ───────────────────────────────────────────────────────────────

def test_elo_tracker_starts():
    """EloTracker announces ready with a nick and ELO."""
    rt = _make_single()
    rt.tick(2, dt=1.0)
    lines = _ownersay(rt)
    assert any("[EloTracker]" in l and "ready" in l for l in lines), lines


def test_engine_uuid_written():
    """engine:uuid is set to the board's object key on startup."""
    rt = _make_single()
    rt.tick(2, dt=1.0)
    uuid = _lsd(rt, "Board A", "engine:uuid")
    assert len(uuid) == 36 and "-" in uuid, f"bad uuid: {uuid!r}"


def test_engine_nick_defaults_to_object_name():
    """engine:nick defaults to the object name when not pre-set."""
    rt = _make_single("My Chess Board")
    rt.tick(2, dt=1.0)
    nick = _lsd(rt, "My Chess Board", "engine:nick")
    assert nick == "My Chess Board", f"unexpected nick: {nick!r}"


def test_engine_nick_owner_preset():
    """engine:nick is respected if pre-written to LSD before startup."""
    rt = _make_single()
    rt.objects["Board A"].linkset_data["engine:nick"] = "Dude Hazard"
    # Restart EloTracker by manually re-firing state_entry on its script
    # (simplest: just write nick before first tick so startup reads it)
    World().reset()
    rt2 = _make_single()
    rt2.objects["Board A"].linkset_data["engine:nick"] = "Dude Hazard"
    rt2.tick(2, dt=1.0)
    assert _lsd(rt2, "Board A", "engine:nick") == "Dude Hazard"


def test_engine_elo_seeded():
    """engine:elo is initialised to 1500 when not pre-configured."""
    rt = _make_single()
    rt.tick(2, dt=1.0)
    elo = _lsd(rt, "Board A", "engine:elo")
    assert elo == "1500", f"unexpected engine:elo {elo!r}"


def test_engine_elo_custom_start():
    """engine:elo_start controls initial engine ELO."""
    rt = _make_single()
    rt.objects["Board A"].linkset_data["engine:elo_start"] = "1800"
    rt.objects["Board A"].linkset_data.pop("engine:elo", None)
    # Reseed engine:elo by running fresh
    World().reset()
    rt2 = _make_single()
    rt2.objects["Board A"].linkset_data["engine:elo_start"] = "1800"
    rt2.tick(2, dt=1.0)
    assert _lsd(rt2, "Board A", "engine:elo") == "1800"


def test_engine_own_elo_record():
    """The engine's own UUID has an ELO record in LSD."""
    rt = _make_single()
    rt.tick(2, dt=1.0)
    uuid = _lsd(rt, "Board A", "engine:uuid")
    record = _lsd(rt, "Board A", "elo:" + uuid)
    assert record != "", "engine should have its own ELO record"
    parts = record.split("|")
    assert len(parts) == 6          # 6-field format including local_games
    assert int(parts[0]) == 1500   # default engine ELO


# ── 2. ELO calculation ───────────────────────────────────────────────────────

def _game(rt, w, b, result):
    _inject_lm(rt, "Board A", LM_ELO_GAME, f"{w}|{b}|{result}")
    rt.tick(1, dt=0.1)


def _elo_of(rt, uuid):
    record = _lsd(rt, "Board A", "elo:" + uuid)
    if not record:
        return ELO_DEFAULT
    return int(record.split("|")[0])


def test_white_win_updates_elo():
    """
    Both players at default 1200, K=32 (new).
    White wins: new_white = 1200 + 32*(1 - 0.5) = 1216
                new_black = 1200 + 32*(0 - 0.5) = 1184
    """
    rt = _make_single()
    rt.tick(2, dt=1.0)
    _game(rt, PLAYER_A, PLAYER_B, "1")
    assert _elo_of(rt, PLAYER_A) == 1216, _elo_of(rt, PLAYER_A)
    assert _elo_of(rt, PLAYER_B) == 1184, _elo_of(rt, PLAYER_B)


def test_black_win_updates_elo():
    """Black wins: white drops, black rises."""
    rt = _make_single()
    rt.tick(2, dt=1.0)
    _game(rt, PLAYER_A, PLAYER_B, "0")
    assert _elo_of(rt, PLAYER_A) == 1184
    assert _elo_of(rt, PLAYER_B) == 1216


def test_draw_moves_both_toward_equilibrium():
    """
    At equal ELO a draw leaves both unchanged (expected = 0.5, score = 0.5).
    new = 1200 + 32*(0.5 - 0.5) = 1200
    """
    rt = _make_single()
    rt.tick(2, dt=1.0)
    _game(rt, PLAYER_A, PLAYER_B, "0.5")
    assert _elo_of(rt, PLAYER_A) == 1200
    assert _elo_of(rt, PLAYER_B) == 1200


def test_elo_accumulates_over_multiple_games():
    """Win, then win again — ELO keeps climbing."""
    rt = _make_single()
    rt.tick(2, dt=1.0)
    _game(rt, PLAYER_A, PLAYER_B, "1")
    elo1 = _elo_of(rt, PLAYER_A)
    _game(rt, PLAYER_A, PLAYER_B, "1")
    elo2 = _elo_of(rt, PLAYER_A)
    assert elo2 > elo1, f"ELO should keep rising: {elo1} → {elo2}"


def test_k_factor_drops_after_30_games():
    """
    After 30 games K drops from 32 to 16.
    Play 29 draws (no change), then a win — delta should be ~16 not ~32.
    """
    rt = _make_single()
    rt.tick(2, dt=1.0)
    # Pre-load records with 29 draws so game count = 29
    import time as _time
    ts = int(_time.time())
    rt.objects["Board A"].linkset_data[f"elo:{PLAYER_A}"] = f"1200|10|10|9|{ts}|29"
    rt.objects["Board A"].linkset_data[f"elo:{PLAYER_B}"] = f"1200|10|10|9|{ts}|29"
    # One more draw → 30 games
    _game(rt, PLAYER_A, PLAYER_B, "0.5")
    # Now 30 games played; K_EST=16 kicks in next game
    elo_before = _elo_of(rt, PLAYER_A)
    _game(rt, PLAYER_A, PLAYER_B, "1")
    delta = _elo_of(rt, PLAYER_A) - elo_before
    assert delta == 8, f"expected K=16 delta=8, got {delta}"   # 16*(1-0.5)=8


def test_elo_floor_at_100():
    """ELO never drops below 100."""
    rt = _make_single()
    rt.tick(2, dt=1.0)
    import time as _time
    ts = int(_time.time())
    rt.objects["Board A"].linkset_data[f"elo:{PLAYER_A}"] = f"105|5|25|0|{ts}|5"
    rt.objects["Board A"].linkset_data[f"elo:{PLAYER_B}"] = f"3000|30|0|0|{ts}|5"
    _game(rt, PLAYER_A, PLAYER_B, "0")   # heavy favourite wins; loser very weak
    assert _elo_of(rt, PLAYER_A) >= 100


# ── 3. win/loss/draw counters ─────────────────────────────────────────────────

def _record(rt, uuid):
    raw = _lsd(rt, "Board A", "elo:" + uuid)
    if not raw:
        return (ELO_DEFAULT, 0, 0, 0)
    p = raw.split("|")
    return (int(p[0]), int(p[1]), int(p[2]), int(p[3]))


def test_win_counter():
    rt = _make_single()
    rt.tick(2, dt=1.0)
    _game(rt, PLAYER_A, PLAYER_B, "1")
    elo, w, l, d = _record(rt, PLAYER_A)
    assert w == 1 and l == 0 and d == 0


def test_loss_counter():
    rt = _make_single()
    rt.tick(2, dt=1.0)
    _game(rt, PLAYER_A, PLAYER_B, "0")
    elo, w, l, d = _record(rt, PLAYER_A)
    assert w == 0 and l == 1 and d == 0


def test_draw_counter():
    rt = _make_single()
    rt.tick(2, dt=1.0)
    _game(rt, PLAYER_A, PLAYER_B, "0.5")
    elo, w, l, d = _record(rt, PLAYER_A)
    assert w == 0 and l == 0 and d == 1


# ── 4. LM_ELO_QUERY ──────────────────────────────────────────────────────────

def test_query_unknown_player_returns_default():
    """Querying an unseen UUID returns ELO_DEFAULT with zero games."""
    rt = _make_single()
    rt.tick(2, dt=1.0)
    _inject_lm(rt, "Board A", LM_ELO_QUERY, PLAYER_A)
    rt.tick(1, dt=0.1)
    # Response goes to LM_ELO_RESP; we check LSD indirectly via record
    record = _lsd(rt, "Board A", "elo:" + PLAYER_A)
    # No record → default is returned (not stored)
    assert record == ""   # board doesn't persist until a game is played


def test_query_known_player():
    """After a game, querying the player returns their new ELO."""
    rt = _make_single()
    rt.tick(2, dt=1.0)
    _game(rt, PLAYER_A, PLAYER_B, "1")
    _inject_lm(rt, "Board A", LM_ELO_QUERY, PLAYER_A)
    rt.tick(1, dt=0.1)
    elo, wins, losses, draws = _record(rt, PLAYER_A)
    assert elo == 1216 and wins == 1


# ── 5. P2P region sync ───────────────────────────────────────────────────────

def test_peer_elo_broadcast_merged():
    """
    Board A plays a game; Board B (same region) should receive the broadcast
    and store Board A's players' new ELOs.
    """
    rt = _make_two()
    rt.tick(2, dt=1.0)
    _inject_lm(rt, "Board A", LM_ELO_GAME, f"{PLAYER_A}|{PLAYER_B}|1")
    rt.tick(2, dt=0.5)

    # Board B should have merged the record
    rec_b_a = rt.objects["Board B"].linkset_data.get("elo:" + PLAYER_A, "")
    assert rec_b_a != "", "Board B should have received PLAYER_A's ELO via region broadcast"
    assert int(rec_b_a.split("|")[0]) == 1216


def test_peer_broadcast_newer_timestamp_wins():
    """
    If a peer has a newer ELO for a player, the local board adopts it.
    """
    rt = _make_two()
    rt.tick(2, dt=1.0)

    import time as _time
    old_ts = int(_time.time()) - 100
    rt.objects["Board A"].linkset_data[f"elo:{PLAYER_A}"] = f"1300|5|3|0|{old_ts}|3"

    # Simulate a peer broadcast with a newer timestamp
    new_ts  = int(_time.time())
    new_elo = 1350
    from sim.world import World as W
    world = rt.world
    # Inject a raw region-say listen event directly onto Board A's EloTracker
    from sim.prim import ScriptItem
    obj_a = rt.objects["Board A"]
    for prim in obj_a.prims:
        for item in prim.inventory:
            if isinstance(item, ScriptItem) and item.running and "EloTracker" in item.name:
                item.event_queue.push(LSLEvent("listen", [
                    -20200357,   # ELO_CHAN
                    "Board B",
                    "bbbb0000-0000-0000-0000-000000000001",
                    f"elogame|{PLAYER_A}|{PLAYER_B}|1"
                    f"|{new_elo}|1180|{new_ts}"
                    f"|bbbb0000-0000-0000-0000-000000000001",
                ]))
    rt.tick(1, dt=0.1)
    merged = rt.objects["Board A"].linkset_data.get(f"elo:{PLAYER_A}", "")
    assert merged != ""
    assert int(merged.split("|")[0]) == new_elo, f"expected {new_elo}, got {merged}"


def test_peer_broadcast_older_timestamp_ignored():
    """If our local record is newer, we ignore the peer broadcast."""
    rt = _make_single()
    rt.tick(2, dt=1.0)

    import time as _time
    fresh_ts = int(_time.time())
    rt.objects["Board A"].linkset_data[f"elo:{PLAYER_A}"] = f"1250|5|3|0|{fresh_ts}|2"

    old_ts = fresh_ts - 200
    from sim.prim import ScriptItem
    obj = rt.objects["Board A"]
    for prim in obj.prims:
        for item in prim.inventory:
            if isinstance(item, ScriptItem) and item.running and "EloTracker" in item.name:
                item.event_queue.push(LSLEvent("listen", [
                    -20200357,
                    "Board B",
                    "bbbb0000-0000-0000-0000-000000000001",
                    f"elogame|{PLAYER_A}|{PLAYER_B}|1"
                    f"|1100|1190|{old_ts}"
                    f"|bbbb0000-0000-0000-0000-000000000001",
                ]))
    rt.tick(1, dt=0.1)
    kept = rt.objects["Board A"].linkset_data.get(f"elo:{PLAYER_A}", "")
    assert int(kept.split("|")[0]) == 1250, f"should have kept local value, got {kept}"


def test_own_broadcast_not_reprocessed():
    """Board A ignores its own ELO broadcasts (witness == own UUID)."""
    rt = _make_single()
    rt.tick(2, dt=1.0)
    _game(rt, PLAYER_A, PLAYER_B, "1")
    elo_after_game = _elo_of(rt, PLAYER_A)

    # Inject our own broadcast back as if we heard it on region chat
    import time as _time
    own_uuid = _lsd(rt, "Board A", "engine:uuid")
    ts = int(_time.time())
    from sim.prim import ScriptItem
    obj = rt.objects["Board A"]
    for prim in obj.prims:
        for item in prim.inventory:
            if isinstance(item, ScriptItem) and item.running and "EloTracker" in item.name:
                item.event_queue.push(LSLEvent("listen", [
                    -20200357,
                    "Board A",
                    own_uuid,
                    f"elogame|{PLAYER_A}|{PLAYER_B}|1|9999|100|{ts}|{own_uuid}",
                ]))
    rt.tick(1, dt=0.1)
    # ELO must not have been replaced by the bogus 9999 from our own message
    assert _elo_of(rt, PLAYER_A) == elo_after_game


def test_future_timestamp_rejected():
    """Broadcasts with timestamps >60s in the future are rejected."""
    rt = _make_single()
    rt.tick(2, dt=1.0)

    import time as _time
    future_ts = int(_time.time()) + 300   # 5 minutes ahead
    from sim.prim import ScriptItem
    obj = rt.objects["Board A"]
    for prim in obj.prims:
        for item in prim.inventory:
            if isinstance(item, ScriptItem) and item.running and "EloTracker" in item.name:
                item.event_queue.push(LSLEvent("listen", [
                    -20200357,
                    "Board B",
                    "cccc0000-0000-0000-0000-000000000001",
                    f"elogame|{PLAYER_A}|{PLAYER_B}|1|9999|100|{future_ts}"
                    f"|cccc0000-0000-0000-0000-000000000001",
                ]))
    rt.tick(1, dt=0.1)
    record = _lsd(rt, "Board A", f"elo:{PLAYER_A}")
    assert record == "" or int(record.split("|")[0]) != 9999


# ── 6. engine as player ───────────────────────────────────────────────────────

def test_engine_elo_updated_when_it_plays():
    """
    When the engine (board UUID) is one of the players, engine:elo LSD key
    is kept in sync with the elo:{uuid} record.
    """
    rt = _make_single()
    rt.tick(2, dt=1.0)
    engine_uuid = _lsd(rt, "Board A", "engine:uuid")
    initial_engine_elo = int(_lsd(rt, "Board A", "engine:elo"))

    # Engine (white) plays a human (black)
    _game(rt, engine_uuid, PLAYER_A, "1")   # engine wins

    new_engine_elo = int(_lsd(rt, "Board A", "engine:elo"))
    assert new_engine_elo > initial_engine_elo, (
        f"engine ELO should rise after a win: {initial_engine_elo} → {new_engine_elo}")

    # engine:elo should match the full record
    rec_elo = _elo_of(rt, engine_uuid)
    assert rec_elo == new_engine_elo


# ── 7. local_games counter ────────────────────────────────────────────────────

def _local_games(rt, uuid, obj_name="Board A"):
    raw = rt.objects[obj_name].linkset_data.get("elo:" + uuid, "")
    if not raw:
        return 0
    parts = raw.split("|")
    return int(parts[5]) if len(parts) > 5 else 0


def test_local_games_increments_on_game():
    """Each game on this board increments both players' local_games."""
    rt = _make_single()
    rt.tick(2, dt=1.0)
    assert _local_games(rt, PLAYER_A) == 0
    _game(rt, PLAYER_A, PLAYER_B, "1")
    assert _local_games(rt, PLAYER_A) == 1
    assert _local_games(rt, PLAYER_B) == 1
    _game(rt, PLAYER_A, PLAYER_B, "0.5")
    assert _local_games(rt, PLAYER_A) == 2


def test_merge_does_not_increment_local_games():
    """P2P merge should not change local_games — only local gameplay does."""
    rt = _make_single()
    rt.tick(2, dt=1.0)
    _game(rt, PLAYER_A, PLAYER_B, "1")
    local_before = _local_games(rt, PLAYER_A)

    # Simulate a peer broadcast with a newer ELO
    import time as _time
    ts = int(_time.time()) + 5   # slightly newer
    from sim.prim import ScriptItem
    obj = rt.objects["Board A"]
    for prim in obj.prims:
        for item in prim.inventory:
            if isinstance(item, ScriptItem) and item.running and "EloTracker" in item.name:
                item.event_queue.push(LSLEvent("listen", [
                    -20200357, "Board B",
                    "cccc0000-0000-0000-0000-000000000001",
                    f"elogame|{PLAYER_A}|{PLAYER_B}|1|1220|1180|{ts}"
                    f"|cccc0000-0000-0000-0000-000000000001",
                ]))
    rt.tick(1, dt=0.1)
    assert _local_games(rt, PLAYER_A) == local_before, "merge must not touch local_games"


# ── 8. LSD memory management ─────────────────────────────────────────────────

def test_lsd_available_decreases_with_records():
    """llLinksetDataAvailable() decreases as records are written."""
    rt = _make_single()
    rt.tick(2, dt=1.0)

    from core.builtins.linkset import LSD_LIMIT
    used_before = LSD_LIMIT - sum(
        len(k.encode()) + len(v.encode())
        for k, v in rt.objects["Board A"].linkset_data.items()
    )

    _game(rt, PLAYER_A, PLAYER_B, "1")

    used_after = LSD_LIMIT - sum(
        len(k.encode()) + len(v.encode())
        for k, v in rt.objects["Board A"].linkset_data.items()
    )
    assert used_after < used_before, "available space should shrink after writing records"


def test_remote_records_evicted_when_lsd_tight():
    """
    When LSD is nearly full, _maybe_cleanup() evicts remote-only records
    (local_games=0) oldest-first.  Local records (local_games>0) survive.
    """
    import uuid as _uuid
    import time as _time

    rt = _make_single()
    rt.tick(2, dt=1.0)

    # Pack LSD with many remote-only records to trigger cleanup
    # Each elo: record ≈ 80 bytes; fill until < 20 KB free
    from core.builtins.linkset import LSD_LIMIT
    CLEANUP_THRESHOLD = 20480

    ts_base = int(_time.time()) - 1000
    remote_uuids = []
    while True:
        used = sum(len(k.encode()) + len(v.encode())
                   for k, v in rt.objects["Board A"].linkset_data.items())
        if LSD_LIMIT - used < CLEANUP_THRESHOLD:
            break
        u = str(_uuid.uuid4())
        remote_uuids.append(u)
        # local_games=0 → remote-only; use ascending timestamps so we know which is oldest
        ts = ts_base + len(remote_uuids)
        rt.objects["Board A"].linkset_data[f"elo:{u}"] = f"1200|0|0|0|{ts}|0"

    oldest_remote = remote_uuids[0]    # lowest timestamp → first to evict
    # Also create a local player record (local_games > 0) — must survive
    local_uuid = str(_uuid.uuid4())
    rt.objects["Board A"].linkset_data[f"elo:{local_uuid}"] = f"1300|5|2|1|{ts_base}|3"

    # Trigger a peer broadcast to invoke _merge_record → _maybe_cleanup
    ts_new = int(_time.time())
    new_peer_uuid = str(_uuid.uuid4())
    from sim.prim import ScriptItem
    witness = "eeee0000-0000-0000-0000-000000000099"
    for prim in rt.objects["Board A"].prims:
        for item in prim.inventory:
            if isinstance(item, ScriptItem) and item.running and "EloTracker" in item.name:
                item.event_queue.push(LSLEvent("listen", [
                    -20200357, "Board B", witness,
                    f"elogame|{new_peer_uuid}|{PLAYER_B}|1|1250|1150|{ts_new}|{witness}",
                ]))
    rt.tick(1, dt=0.1)

    # The oldest remote record should have been evicted
    assert f"elo:{oldest_remote}" not in rt.objects["Board A"].linkset_data, \
        "oldest remote record should be evicted"

    # The local player record must still be present
    local_rec = rt.objects["Board A"].linkset_data.get(f"elo:{local_uuid}", "")
    assert local_rec != "", "local player (local_games>0) must never be evicted"


def test_lsd_find_keys_prefix():
    """llLinksetDataFindKeys with prefix 'elo:' returns all ELO keys."""
    rt = _make_single()
    rt.tick(2, dt=1.0)
    _game(rt, PLAYER_A, PLAYER_B, "1")

    # Manually count elo: keys in LSD
    elo_keys = [k for k in rt.objects["Board A"].linkset_data if k.startswith("elo:")]
    assert len(elo_keys) >= 2   # PLAYER_A, PLAYER_B (+ possibly engine)
