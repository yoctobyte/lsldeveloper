import csv
from pathlib import Path

from core.builtins.runtime import HANDLED_FUNCTIONS


def test_function_status_covers_current_interpreter_handlers():
    with Path("data/lsl_functions_status.csv").open(encoding="utf-8", newline="") as f:
        rows = {row["name"]: row for row in csv.DictReader(f)}

    missing_from_table = HANDLED_FUNCTIONS - set(rows)
    marked_missing = {name for name in HANDLED_FUNCTIONS if rows[name]["status"] == "missing"}

    assert not missing_from_table
    assert not marked_missing


def test_function_status_has_official_function_count():
    with Path("data/lsl_functions_status.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 520
