from core.interpreter import ExecutionContext
from core.lslconstants import LSL_CONSTANTS, default_globals
from core.types import NULL_KEY


def test_execution_context_seeds_lsl_constants_from_dedicated_module():
    ctx = ExecutionContext()

    assert ctx.globals["NULL_KEY"] == NULL_KEY
    assert ctx.globals["INVENTORY_SCRIPT"] == 10
    assert ctx.globals["PRIM_NAME"] == 27
    assert ctx.globals["OBJECT_NAME"] == "OBJECT_NAME"
    assert ctx.globals["PARCEL_DETAILS_NAME"] == "PARCEL_DETAILS_NAME"


def test_default_globals_returns_a_copy():
    first = default_globals()
    second = default_globals()

    first["TRUE"] = 99

    assert LSL_CONSTANTS["TRUE"] == 1
    assert second["TRUE"] == 1
