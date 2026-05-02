from __future__ import annotations

import uuid

from events.queue import LSLEvent

from .inventory import _item_by_name
from .registry import builtin


@builtin("llGetNotecardLine")
def ll_get_notecard_line(evaluator, args):
    request_id = str(uuid.uuid4())
    script = evaluator.script
    item = _item_by_name(script, str(args[0]))
    line_index = int(args[1])
    data = "EOF"
    if item and hasattr(item, "lines") and 0 <= line_index < len(item.lines):
        data = item.lines[line_index]
    if script:
        script.event_queue.push(LSLEvent("dataserver", [request_id, data]))
    return request_id


@builtin("llGetNumberOfNotecardLines")
def ll_get_number_of_notecard_lines(evaluator, args):
    request_id = str(uuid.uuid4())
    script = evaluator.script
    item = _item_by_name(script, str(args[0]))
    count = len(getattr(item, "lines", [])) if item else 0
    if script:
        script.event_queue.push(LSLEvent("dataserver", [request_id, str(count)]))
    return request_id
