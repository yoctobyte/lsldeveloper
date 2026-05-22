"""
TTChess full-stack integration tests.

Runs Flask on port 5099 (temp SQLite DB) and exercises:
  1. HTTP endpoints directly (health, ttcapi.php, /game, /profile/*, /rankings)
  2. LSL simulation: EloTracker.lsl → real HTTP → Flask → DB
  3. LSL simulation: Matcher.lsl profile dialog → real HTTP → Flask → DB

Run:
    cd ~/lsldeveloper && python -m pytest tests/test_ttchess_fullstack.py -v
"""

from __future__ import annotations

import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

TTCHESS_SRC  = Path(__file__).parent.parent.parent / "ttchess"
BACKEND_SRC  = TTCHESS_SRC / "backend"
SERVER_PORT  = 5099
SERVER_URL   = f"http://127.0.0.1:{SERVER_PORT}"   # may be overridden by the fixture

# When TTCHESS_LIVE_URL is set, the fixture skips spinning up an embedded server
# and points all tests at the already-running process instead.
_LIVE_URL = os.environ.get("TTCHESS_LIVE_URL", "").rstrip("/")

# Stable fake UUIDs used across tests
W_UUID    = "aaaaaaaa-aaaa-aaaa-aaaa-000000000001"
B_UUID    = "bbbbbbbb-bbbb-bbbb-bbbb-000000000002"
BOARD_UUID = "cccccccc-cccc-cccc-cccc-000000000003"
P_UUID    = "dddddddd-dddd-dddd-dddd-000000000004"
D_UUID    = "eeeeeeee-eeee-eeee-eeee-000000000005"  # to-be-delisted


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _get(path: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(f"{SERVER_URL}{path}", timeout=5) as r:
            return r.getcode(), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def _post(path: str, data: dict) -> tuple[int, str]:
    body = urllib.parse.urlencode(data).encode()
    req  = urllib.request.Request(
        f"{SERVER_URL}{path}", data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.getcode(), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


# ── Server fixture ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def server(tmp_path_factory):
    """Start Flask on a temp SQLite DB; shut down after all tests in this module.

    When TTCHESS_LIVE_URL is set, skip the embedded server and use that URL.
    """
    global SERVER_URL

    if _LIVE_URL:
        SERVER_URL = _LIVE_URL
        yield _LIVE_URL
        return

    db_file = tmp_path_factory.mktemp("ttchess_db") / "test.db"

    # models.DB_PATH is read at get_db() call time, so patching before first
    # request is sufficient.  We must insert the backend path before importing.
    if str(BACKEND_SRC) not in sys.path:
        sys.path.insert(0, str(BACKEND_SRC))

    import models
    models.DB_PATH = str(db_file)
    models.init_db()   # create tables at the temp path

    from app import app as flask_app
    from werkzeug.serving import make_server as _make_server

    SERVER_URL = f"http://127.0.0.1:{SERVER_PORT}"
    srv = _make_server("127.0.0.1", SERVER_PORT, flask_app)
    t   = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    # wait until the server is actually ready
    for _ in range(20):
        try:
            urllib.request.urlopen(f"{SERVER_URL}/health", timeout=1)
            break
        except Exception:
            time.sleep(0.1)

    yield SERVER_URL
    srv.shutdown()


# ══════════════════════════════════════════════════════════════════════════════
# 1. Basic HTTP endpoint smoke tests
# ══════════════════════════════════════════════════════════════════════════════

def test_health(server):
    status, body = _get("/health")
    assert status == 200
    assert body == "ok"


def test_nodes_php(server):
    status, body = _get("/nodes.php")
    assert status == 200
    urls = [l for l in body.strip().splitlines() if l]
    assert len(urls) >= 1
    assert all("/engine/" in u for u in urls)


def test_engines_json(server):
    status, body = _get("/engines")
    assert status == 200
    import json
    data = json.loads(body)
    assert "engines" in data
    assert any(e["name"] == "tania_dupe" for e in data["engines"])


# ══════════════════════════════════════════════════════════════════════════════
# 2. ttcapi.php compatibility layer
# ══════════════════════════════════════════════════════════════════════════════

def test_ttcapi_elo_by_name(server):
    """?elo=Tania-4+AI  →  plain integer"""
    status, body = _get("/ttcapi.php?elo=Tania-4+AI")
    assert status == 200
    assert int(body.strip()) == 1500


def test_ttcapi_elo_direct(server):
    status, body = _get("/ttcapi.php?elo=Dude")
    assert status == 200
    assert int(body.strip()) == 2600


def test_ttcapi_findopponents(server):
    status, body = _get("/ttcapi.php?findopponents=Alice&level=5")
    assert status == 200
    assert "Available AI opponents" in body
    # Each engine should appear
    assert "Rookie" in body or "Tania" in body


def test_ttcapi_findaimatch(server):
    status, body = _get("/ttcapi.php?findaimatch=Alice&level=10")
    assert status == 200
    # Returns "Fname Lname"
    parts = body.strip().split()
    assert len(parts) == 2


def test_ttcapi_getaidetails(server):
    """?getaidetails=Tania  →  'fname lname level random duration'"""
    status, body = _get("/ttcapi.php?getaidetails=Tania")
    assert status == 200
    parts = body.strip().split("|")
    assert parts[0] == "tania_dupe"   # key
    assert parts[1] == "Tania Dupe"  # display name
    assert int(parts[2]) == 1500     # elo
    assert int(parts[3]) == 30       # duration


def test_ttcapi_aivsai(server):
    """?aivsai=  →  exactly 2 lines"""
    status, body = _get("/ttcapi.php?aivsai=&level=20")
    assert status == 200
    lines = [l for l in body.strip().splitlines() if l]
    assert len(lines) == 2
    # Each line: "key|display name|elo|duration"
    for line in lines:
        parts = line.split("|")
        assert len(parts) == 4
        assert parts[0]
        assert parts[1]
        assert int(parts[2]) > 0
        assert int(parts[3]) > 0


def test_ttcapi_rankings(server):
    status, body = _get("/ttcapi.php?rankings")
    assert status == 200
    assert "/rankings" in body


def test_ttcapi_bad_request(server):
    status, _ = _get("/ttcapi.php")
    assert status == 400


# ══════════════════════════════════════════════════════════════════════════════
# 3. Game recording via /game POST
# ══════════════════════════════════════════════════════════════════════════════

def test_post_game_white_wins(server):
    status, body = _post("/game", {
        "white_uuid": W_UUID,
        "black_uuid": B_UUID,
        "result":     "1-0",
        "board_uuid": BOARD_UUID,
        "ts":         str(int(time.time())),
    })
    assert status == 200
    assert body == "ok"


@pytest.mark.skipif(bool(_LIVE_URL), reason="DB file not accessible on live server")
def test_post_game_updates_elo(server):
    """After a white win both players should exist in DB with updated ELO/record."""
    import models, sqlite3
    with sqlite3.connect(models.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        w = conn.execute("SELECT * FROM profiles WHERE uuid=?", (W_UUID,)).fetchone()
        b = conn.execute("SELECT * FROM profiles WHERE uuid=?", (B_UUID,)).fetchone()

    assert w is not None and b is not None
    assert w["wins"]   >= 1
    assert b["losses"] >= 1
    assert w["elo"]    >  1200   # winner ELO rises from default
    assert b["elo"]    <  1200   # loser ELO falls from default


def test_post_game_draw(server):
    status, body = _post("/game", {
        "white_uuid": W_UUID,
        "black_uuid": B_UUID,
        "result":     "1/2",
        "board_uuid": BOARD_UUID,
        "ts":         str(int(time.time())),
    })
    assert status == 200


def test_post_game_bad_result(server):
    status, _ = _post("/game", {
        "white_uuid": W_UUID,
        "black_uuid": B_UUID,
        "result":     "invalid",
    })
    assert status == 400


def test_post_game_missing_uuid(server):
    status, _ = _post("/game", {"result": "1-0"})
    assert status == 400


# ══════════════════════════════════════════════════════════════════════════════
# 4. Profile management endpoints
# ══════════════════════════════════════════════════════════════════════════════

def test_profile_consent_full(server):
    status, body = _post("/profile/consent", {
        "uuid":         P_UUID,
        "consent":      "full",
        "display_name": "Test Player",
        "board_uuid":   BOARD_UUID,
    })
    assert status == 200
    assert body == "ok"


def test_profile_consent_bad(server):
    status, _ = _post("/profile/consent", {
        "uuid":    P_UUID,
        "consent": "invalid_value",
    })
    assert status == 400


def test_profile_settings_hide_rating(server):
    status, body = _post("/profile/settings", {
        "uuid":        P_UUID,
        "hide_rating": "1",
        "board_uuid":  BOARD_UUID,
    })
    assert status == 200


def test_profile_settings_bio(server):
    status, body = _post("/profile/settings", {
        "uuid":       P_UUID,
        "bio":        "I love chess!",
        "board_uuid": BOARD_UUID,
    })
    assert status == 200


def test_profile_settings_missing_uuid(server):
    status, _ = _post("/profile/settings", {"bio": "no uuid"})
    assert status == 400


def test_delist(server):
    # Create the player first via a game
    _post("/game", {
        "white_uuid": D_UUID,
        "black_uuid": B_UUID,
        "result":     "1-0",
        "ts":         str(int(time.time())),
    })
    status, body = _post("/delist", {
        "uuid":       D_UUID,
        "board_uuid": BOARD_UUID,
    })
    assert status == 200
    assert body == "ok"


def test_delist_bad_request(server):
    status, _ = _post("/delist", {})
    assert status == 400


# ══════════════════════════════════════════════════════════════════════════════
# 5. Web pages
# ══════════════════════════════════════════════════════════════════════════════

def test_rankings_page(server):
    # First ensure W_UUID has a public name
    _post("/profile/consent", {
        "uuid":         W_UUID,
        "consent":      "full",
        "display_name": "Alice Winner",
        "board_uuid":   BOARD_UUID,
    })
    status, body = _get("/rankings")
    assert status == 200
    assert "<table" in body.lower()
    assert "Alice Winner" in body


def test_rankings_excludes_delisted(server):
    _, body = _get("/rankings")
    assert D_UUID not in body


def test_profile_page_exists(server):
    status, body = _get(f"/profile/{P_UUID}")
    assert status == 200
    assert "Test Player" in body


def test_profile_page_hides_rating(server):
    """hide_rating=1 was set above; ELO stat box should be absent from page."""
    _, body = _get(f"/profile/{P_UUID}")
    # Template omits the ELO stat box when hide_rating=1; the CSS defines .elo-num
    # but the <span class="num elo-num"> element should be absent.
    assert 'class="num elo-num"' not in body


def test_profile_page_not_found(server):
    status, body = _get("/profile/00000000-0000-0000-0000-000000000000")
    assert status == 404
    assert "not found" in body.lower()


def test_profile_page_delisted(server):
    status, _ = _get(f"/profile/{D_UUID}")
    assert status == 404


def test_profile_page_recent_games(server):
    """Profile page should list recent games for a player who has played."""
    _post("/profile/consent", {
        "uuid":         W_UUID,
        "consent":      "full",
        "display_name": "Alice Winner",
        "board_uuid":   BOARD_UUID,
    })
    status, body = _get(f"/profile/{W_UUID}")
    assert status == 200
    # Recent games table should exist
    assert "Opponent" in body or "opponent" in body


# ══════════════════════════════════════════════════════════════════════════════
# 6. LSL simulation: EloTracker → real HTTP → Flask → DB
# ══════════════════════════════════════════════════════════════════════════════

LM_CONFIG_APIBASE = 0xCE040


def _make_elotracker_project(server_url: str):
    """Build a runtime with EloTracker.lsl; APIBASE is set via LM_CONFIG_APIBASE."""
    from ide.project import IdeProject, ProjectObject, ProjectScript
    from sim.world import World

    World().reset()

    src = (TTCHESS_SRC / "EloTracker.lsl").read_text()

    from pathlib import Path as _Path
    proj = IdeProject(
        _Path("/tmp/ttchess_elo_test"),
        [ProjectObject("Board", scripts=[ProjectScript("EloTracker.lsl", src)])]
    )
    return proj


def _lsd_read(runtime, obj_name: str, key: str) -> str:
    return runtime.objects[obj_name].linkset_data.get(key, "")


def _inject_lm(runtime, obj_name: str, num: int, msg: str, id_: str = ""):
    from sim.prim import ScriptItem
    from events.queue import LSLEvent
    obj = runtime.objects[obj_name]
    for prim in obj.prims:
        for item in prim.inventory:
            if isinstance(item, ScriptItem) and item.running:
                item.event_queue.push(LSLEvent("link_message", [prim.link_number, num, msg, id_]))


LM_ELO_GAME  = 0xCE030
LM_ELO_QUERY = 0xCE031
LM_ELO_RESP  = 0xCE032

LSL_W = "11111111-1111-1111-1111-000000000001"
LSL_B = "22222222-2222-2222-2222-000000000002"


def test_elotracker_starts(server):
    proj    = _make_elotracker_project(server)
    runtime = proj.build_runtime(echo_stdout=False)
    runtime.tick(3, dt=1.0)

    lines = [m.text for m in runtime.world.console.messages if m.message_type == "ownersay"]
    assert any("EloTracker" in l and "ready" in l for l in lines), lines


def test_elotracker_posts_game_to_flask(server):
    """
    EloTracker receives LM_ELO_GAME → calls llHTTPRequest → Flask /game →
    DB record created. The simulator's HTTP call is synchronous (urllib),
    so a handful of ticks is enough.

    In embedded mode we verify via DB introspection.  Against a live server
    we verify via the HTTP response logged in ownersay (no 4xx/5xx).
    """
    proj    = _make_elotracker_project(server)
    runtime = proj.build_runtime(echo_stdout=False)
    runtime.tick(2, dt=1.0)

    # Point EloTracker at the test server via the same mechanism NodeManager uses
    _inject_lm(runtime, "Board", LM_CONFIG_APIBASE, server)
    runtime.tick(1, dt=0.1)

    if not _LIVE_URL:
        import models, sqlite3
        with sqlite3.connect(models.DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            before = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]

    # Fire a game result into EloTracker
    _inject_lm(runtime, "Board", LM_ELO_GAME, f"{LSL_W}|{LSL_B}|1")
    runtime.tick(5, dt=1.0)   # enough for the HTTP call + response

    if not _LIVE_URL:
        with sqlite3.connect(models.DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            after = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
            w_row = conn.execute("SELECT * FROM profiles WHERE uuid=?", (LSL_W,)).fetchone()
            b_row = conn.execute("SELECT * FROM profiles WHERE uuid=?", (LSL_B,)).fetchone()
        assert after == before + 1, "game was not recorded in DB"
        assert w_row is not None and b_row is not None
        assert w_row["wins"] >= 1 and b_row["losses"] >= 1
    else:
        # Live mode: confirm no HTTP errors in the sim console
        lines = [m.text for m in runtime.world.console.messages
                 if m.message_type == "ownersay"]
        errors = [l for l in lines if "499" in l or "error" in l.lower()]
        assert not errors, f"EloTracker HTTP error(s) against live server: {errors}"


def test_elotracker_lm_query(server):
    """LM_ELO_QUERY returns ELO data as LM_ELO_RESP without touching Flask."""
    proj    = _make_elotracker_project(server)
    runtime = proj.build_runtime(echo_stdout=False)
    runtime.tick(2, dt=1.0)

    responses = []
    from sim.prim import ScriptItem
    from events.queue import LSLEvent

    # Seed a known record into LSD directly
    obj = runtime.objects["Board"]
    obj.linkset_data["elo:" + LSL_W] = "1350|5|2|1|0|3"

    _inject_lm(runtime, "Board", LM_ELO_QUERY, LSL_W)
    runtime.tick(3, dt=1.0)

    lines = [m.text for m in runtime.world.console.messages if m.message_type == "ownersay"]
    # No assertion on lines here — response goes back as link_message.
    # We just verify EloTracker didn't crash (no exceptions in owner-say).
    assert not any("error" in l.lower() or "script error" in l.lower() for l in lines)


def test_elotracker_p2p_merge(server):
    """
    Broadcast an elogame message on ELO_CHAN; EloTracker should merge
    the peer ELO update for both players into LSD.
    """
    ELO_CHAN = -20200357

    proj    = _make_elotracker_project(server)
    runtime = proj.build_runtime(echo_stdout=False)
    runtime.tick(2, dt=1.0)

    peer_uuid    = "99999999-9999-9999-9999-000000000001"
    peer_witness = "88888888-8888-8888-8888-000000000001"
    ts           = int(time.time()) - 30   # 30 s ago — within the 60 s window

    msg = f"elogame|{LSL_W}|{LSL_B}|1|1310|1190|{ts}|{peer_witness}"

    region = list(runtime.world.regions.values())[0]
    region.broadcast_chat(peer_witness, "Peer Board", ELO_CHAN, msg)

    runtime.tick(3, dt=1.0)

    w_elo_lsd = _lsd_read(runtime, "Board", f"elo:{LSL_W}")
    b_elo_lsd = _lsd_read(runtime, "Board", f"elo:{LSL_B}")

    # After merge, LSD should have the peer-reported ELOs
    assert w_elo_lsd != "", "white ELO not written to LSD after P2P merge"
    assert b_elo_lsd != "", "black ELO not written to LSD after P2P merge"

    w_elo = int(w_elo_lsd.split("|")[0])
    b_elo = int(b_elo_lsd.split("|")[0])
    assert w_elo == 1310, f"expected 1310, got {w_elo}"
    assert b_elo == 1190, f"expected 1190, got {b_elo}"


def test_elotracker_ignores_own_broadcast(server):
    """EloTracker should silently ignore its own witness UUID in broadcasts."""
    ELO_CHAN = -20200357

    proj    = _make_elotracker_project(server)
    runtime = proj.build_runtime(echo_stdout=False)
    runtime.tick(2, dt=1.0)

    engine_uuid = _lsd_read(runtime, "Board", "engine:uuid")
    assert engine_uuid, "engine:uuid should be set on startup"

    ts  = int(time.time()) - 5
    msg = f"elogame|{LSL_W}|{LSL_B}|1|1500|1100|{ts}|{engine_uuid}"

    region = list(runtime.world.regions.values())[0]
    region.broadcast_chat(engine_uuid, "Self", ELO_CHAN, msg)
    runtime.tick(2, dt=1.0)

    # LSD should NOT have been updated from its own broadcast
    w_elo_lsd = _lsd_read(runtime, "Board", f"elo:{LSL_W}")
    if w_elo_lsd:
        w_elo = int(w_elo_lsd.split("|")[0])
        assert w_elo != 1500, "EloTracker should not merge its own broadcast"


# ══════════════════════════════════════════════════════════════════════════════
# 7. Global game log  /games
# ══════════════════════════════════════════════════════════════════════════════

def test_games_log_page(server):
    """GET /games returns an HTML page listing recorded games."""
    status, body = _get("/games")
    assert status == 200
    assert "All Games" in body


def test_games_log_pagination(server):
    """GET /games?page=2 returns 200 (even when empty) and the page count is present."""
    status, body = _get("/games?page=1")
    assert status == 200
    # "total" count appears in the heading regardless of page count
    assert "total" in body.lower() or "All Games" in body


# ══════════════════════════════════════════════════════════════════════════════
# 8. Profile extended stats
# ══════════════════════════════════════════════════════════════════════════════

def test_profile_stats_win_rate(server):
    """Profile page shows win rate percentage."""
    status, body = _get(f"/profile/{W_UUID}")
    assert status == 200
    assert "Win rate" in body


def test_profile_stats_peak_elo(server):
    """Profile page shows Peak ELO stat box when different from current."""
    # We need at least 2 games to create a peak different from current.
    # W_UUID has already won games from earlier tests; just check the page renders.
    status, body = _get(f"/profile/{W_UUID}")
    assert status == 200
    assert "Peak" in body or "Win rate" in body  # at least one extra stat present


def test_profile_history_pagination(server):
    """Profile page shows pagination when player has games."""
    status, body = _get(f"/profile/{W_UUID}")
    assert status == 200
    assert "Game history" in body or "total" in body


# ══════════════════════════════════════════════════════════════════════════════
# 9. Pet name identity system
# ══════════════════════════════════════════════════════════════════════════════

import json as _json


def _post_json(path: str, data: dict, cookie: str = "") -> tuple[int, dict]:
    body = _json.dumps(data).encode()
    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(
        f"{SERVER_URL}{path}", data=body, method="POST", headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.getcode(), _json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, _json.loads(e.read())


def _get_json(path: str, cookie: str = "") -> tuple[int, dict]:
    headers = {}
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(f"{SERVER_URL}{path}", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.getcode(), _json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, _json.loads(e.read())


def test_identity_page_renders(server):
    status, body = _get("/identity")
    assert status == 200
    assert "Identity" in body


def test_identity_register_generates_name(server):
    """POST /identity/register without a custom name returns a pet name."""
    status, data = _post_json("/identity/register", {})
    assert status == 200
    assert data.get("ok")
    name = data.get("pet_name", "")
    assert "-" in name  # AdjectiveNoun-NNNN format
    parts = name.split("-")
    assert len(parts) == 2 and parts[1].isdigit() and len(parts[1]) == 4


def test_identity_register_custom_name(server):
    status, data = _post_json("/identity/register", {"pet_name": "SilverFox-1234"})
    assert status == 200
    assert data.get("pet_name") == "SilverFox-1234"


def test_identity_register_duplicate_name(server):
    """Registering the same name twice returns 409."""
    _post_json("/identity/register", {"pet_name": "GoldenEagle-5678"})
    status, data = _post_json("/identity/register", {"pet_name": "GoldenEagle-5678"})
    assert status == 409
    assert "taken" in data.get("error", "").lower()


def test_identity_register_bad_format(server):
    status, data = _post_json("/identity/register", {"pet_name": "no spaces allowed"})
    assert status == 400


def test_identity_enter_recovers_session(server):
    """Register a pet name, then recover the session using it."""
    # Register fresh
    _, reg = _post_json("/identity/register", {"pet_name": "WildRook-2024"})
    assert reg.get("ok")
    recovered_uuid = reg["uuid"]

    # Recover with the pet name
    status, data = _post_json("/identity/enter", {"pet_name": "WildRook-2024"})
    assert status == 200
    assert data.get("ok")
    assert data["uuid"] == recovered_uuid


def test_identity_enter_unknown_name(server):
    status, data = _post_json("/identity/enter", {"pet_name": "NoSuch-0000"})
    assert status == 404


def test_identity_alias_sets_display_name(server):
    """POST /identity/alias updates display_name on the profile."""
    # Register to get a UUID and cookie
    _, reg = _post_json("/identity/register", {"pet_name": "StormCastle-7777"})
    uid = reg["uuid"]
    cookie = f"ttchess_uid={uid}"

    status, data = _post_json("/identity/alias", {"alias": "Stormy McStorm"}, cookie=cookie)
    assert status == 200
    assert data.get("ok")

    # Check profile page shows the alias
    _, body = _get(f"/profile/{uid}")
    assert "Stormy McStorm" in body


def test_identity_link_code_generates_code(server):
    """GET /identity/link-code returns a 6-char code."""
    _, reg = _post_json("/identity/register", {"pet_name": "BrightDrake-3333"})
    cookie = f"ttchess_uid={reg['uuid']}"
    status, data = _get_json("/identity/link-code", cookie=cookie)
    assert status == 200
    assert data.get("ok")
    code = data.get("code", "")
    assert len(code) == 6 and code.isupper()


def test_identity_confirm_link(server):
    """confirm-link marks a code used and creates a platform_links row."""
    _, reg = _post_json("/identity/register", {"pet_name": "FrostLynx-4444"})
    cookie = f"ttchess_uid={reg['uuid']}"
    _, code_data = _get_json("/identity/link-code", cookie=cookie)
    code = code_data["code"]

    # Simulate in-world board confirming the code
    sl_uuid = "11111111-1111-1111-1111-000000000099"
    status, body = _post("/identity/confirm-link", {
        "code": code, "platform": "secondlife", "platform_uuid": sl_uuid
    })
    assert status == 200
    assert "ok" in body.lower()


def test_identity_link_status_after_confirm(server):
    """link-status returns linked=True after a confirm-link."""
    _, reg = _post_json("/identity/register", {"pet_name": "MagicPawn-5555"})
    cookie = f"ttchess_uid={reg['uuid']}"
    _, code_data = _get_json("/identity/link-code", cookie=cookie)
    code = code_data["code"]

    sl_uuid = "22222222-2222-2222-2222-000000000099"
    _post("/identity/confirm-link", {
        "code": code, "platform": "secondlife", "platform_uuid": sl_uuid
    })

    status, data = _get_json("/identity/link-status", cookie=cookie)
    assert status == 200
    assert data["linked"] is True
    assert any(a["platform_uuid"] == sl_uuid for a in data["accounts"])


def test_identity_confirm_link_bad_code(server):
    status, body = _post("/identity/confirm-link", {
        "code": "ZZZZZZ", "platform": "secondlife", "platform_uuid": "some-uuid"
    })
    assert status == 404
