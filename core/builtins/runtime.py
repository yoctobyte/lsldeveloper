from __future__ import annotations

from .common import UNHANDLED
from .registry import REGISTRY, call_builtin

# Import modules for registration side effects. Runtime remains the stable public
# entry point used by the interpreter, tests, and status tooling.
from . import chat as _chat
from . import dataserver as _dataserver
from . import effects as _effects
from . import http as _http
from . import inventory as _inventory
from . import json_api as _json_api
from . import linkset as _linkset
from . import lists as _lists
from . import object_api as _object_api
from . import parcel as _parcel
from . import primitive as _primitive
from . import region_api as _region_api
from . import rez as _rez
from . import sensors as _sensors
from . import math_api as _math_api
from . import strings as _strings
from . import time_api as _time_api
from . import script_control as _script_control
from .sensors import queue_sensor_event

# stubs must be imported last so that it only stubs out functions that weren't already registered
from . import stubs as _stubs
from .stubs import REGISTERED_STUBS


HANDLED_FUNCTIONS = set(REGISTRY)
STUBBED_FUNCTIONS = set(REGISTERED_STUBS)


__all__ = [
    "HANDLED_FUNCTIONS",
    "STUBBED_FUNCTIONS",
    "UNHANDLED",
    "call_builtin",
    "queue_sensor_event",
]
