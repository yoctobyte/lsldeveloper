from __future__ import annotations

import uuid

from events.queue import LSLEvent

from .common import current_object, current_region
from .registry import builtin

# Synthetic URL_REQUEST_GRANTED / DENIED keys (match lslconstants.py)
_URL_GRANTED = "10000000-0000-0000-0000-000000000001"
_URL_DENIED   = "10000000-0000-0000-0000-000000000002"


def _world():
    from sim.world import World
    return World()


# ── llRequestURL ───────────────────────────────────────────────────────────
@builtin("llRequestURL")
def ll_request_url(evaluator, args):
    script = evaluator.script
    world = _world()
    url = world.register_url(script)
    # Fire async http_request: id=URL_REQUEST_GRANTED, method="", body=url
    if script:
        script.event_queue.push(LSLEvent("http_request", [_URL_GRANTED, "", url]))
    return _URL_GRANTED  # return value rarely used in LSL


@builtin("llReleaseURL")
def ll_release_url(evaluator, args):
    url = str(args[0])
    _world().release_url(url)
    return None


# ── llHTTPResponse ─────────────────────────────────────────────────────────
# Routes a response back to whichever script made the matching llHTTPRequest.
@builtin("llHTTPResponse")
def ll_http_response(evaluator, args):
    serve_key = str(args[0])
    status    = int(args[1])
    body      = str(args[2])
    world     = _world()
    pending   = world.resolve_pending_http(serve_key)
    if pending is None:
        return None
    caller_script, caller_key = pending
    if caller_script:
        caller_script.event_queue.push(
            LSLEvent("http_response", [caller_key, status, [], body])
        )
    return None


# ── llHTTPRequest ──────────────────────────────────────────────────────────
# If the target URL was issued by the simulator (intra-sim routing), the
# request is delivered directly as an http_request event on the target script
# and llHTTPResponse routes the reply back.  External URLs use urllib as before.
@builtin("llHTTPRequest")
def ll_http_request(evaluator, args):
    caller_key = str(uuid.uuid4())
    script = evaluator.script
    world  = _world()

    url    = str(args[0])
    opts   = args[1]
    body   = str(args[2])

    # ── Intra-sim routing ──────────────────────────────────────────────────
    if world.is_sim_url(url):
        target_script = world.resolve_url(url)
        if target_script is None:
            # URL not registered — respond 404
            if script:
                script.event_queue.push(
                    LSLEvent("http_response", [caller_key, 404, [], "not found"])
                )
            return caller_key

        method = "GET"
        for i in range(0, len(opts) - 1, 2):
            if opts[i] == "HTTP_METHOD":
                method = str(opts[i + 1])

        serve_key = str(uuid.uuid4())
        world.register_pending_http(serve_key, script, caller_key)
        target_script.event_queue.push(
            LSLEvent("http_request", [serve_key, method, body])
        )
        return caller_key

    # ── Real outbound HTTP ─────────────────────────────────────────────────
    try:
        import urllib.error
        import urllib.request

        method = "GET"
        for i in range(0, len(opts) - 1, 2):
            if opts[i] == "HTTP_METHOD":
                method = str(opts[i + 1])

        data = None if method == "GET" else body.encode("utf-8")
        req  = urllib.request.Request(url, data=data, method=method)
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_body = resp.read().decode("utf-8", errors="replace")
            status    = resp.getcode() or 200
        if script:
            script.event_queue.push(LSLEvent("http_response", [caller_key, status, [], resp_body]))
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode("utf-8", errors="replace")
        if script:
            script.event_queue.push(LSLEvent("http_response", [caller_key, e.code, [], resp_body]))
    except Exception as e:
        if script:
            script.event_queue.push(LSLEvent("http_response", [caller_key, 499, [], str(e)]))

    return caller_key
