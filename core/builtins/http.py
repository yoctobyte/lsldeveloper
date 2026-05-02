from __future__ import annotations

import uuid

from events.queue import LSLEvent

from .registry import builtin


@builtin("llHTTPRequest")
def ll_http_request(evaluator, args):
    req_id = str(uuid.uuid4())
    script = evaluator.script
    try:
        import urllib.error
        import urllib.request

        url = str(args[0])
        options = args[1]
        body = str(args[2])
        method = "GET"
        for index in range(0, len(options), 2):
            if options[index] == "HTTP_METHOD":
                method = options[index + 1]

        data = None if method == "GET" else body.encode("utf-8")
        request = urllib.request.Request(url, data=data, method=method)
        with urllib.request.urlopen(request, timeout=5) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            status = response.getcode() or 200
        if script:
            script.event_queue.push(LSLEvent("http_response", [req_id, status, [], response_body]))
    except urllib.error.HTTPError as e:
        response_body = e.read().decode("utf-8", errors="replace")
        if script:
            script.event_queue.push(LSLEvent("http_response", [req_id, e.code, [], response_body]))
    except Exception as e:
        if script:
            script.event_queue.push(LSLEvent("http_response", [req_id, 499, [], str(e)]))
    return req_id
