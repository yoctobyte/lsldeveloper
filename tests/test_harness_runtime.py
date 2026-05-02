from harness.cli import main
from harness.runtime import build_runtime


SCRIPT = """
integer hits;
integer exited;

default {
    state_entry() {
        llSetTimerEvent(0.2);
    }

    state_exit() {
        exited = 1;
    }

    touch_start(integer total_number) {
        do {
            hits++;
        } while (hits < total_number);
    }

    timer() {
        state done;
    }
}

state done {
    state_entry() {
        llSetTimerEvent(0.0);
    }
}
"""


def test_offline_runtime_runs_events_state_exit_and_do_while():
    runtime = build_runtime(SCRIPT)

    runtime.tick()
    runtime.touch()
    runtime.tick()
    runtime.tick(3, 0.1)

    assert runtime.script.ctx.globals["hits"] == 1
    assert runtime.script.ctx.globals["exited"] == 1
    assert runtime.script.current_state == "done"


def test_cli_check_and_run(tmp_path, capsys):
    script_path = tmp_path / "demo.lsl"
    script_path.write_text(
        """
default {
    state_entry() {
        llOwnerSay("ready");
    }
}
""",
        encoding="utf-8",
    )

    assert main(["--check", str(script_path)]) == 0
    assert "OK: parsed" in capsys.readouterr().out

    assert main([str(script_path), "--ticks", "0"]) == 0
    out = capsys.readouterr().out
    assert "OWNER_SAY: ready" in out
    assert "OK: ran" in out
