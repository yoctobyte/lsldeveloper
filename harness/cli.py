from __future__ import annotations

import argparse
from pathlib import Path

from .runtime import build_runtime, parse_lsl


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lsl-dev",
        description="Parse and run LSL scripts in the offline Python simulator.",
    )
    parser.add_argument("script", nargs="?", help="Path to an LSL script")
    parser.add_argument("--check", action="store_true", help="Only parse the script")
    parser.add_argument("--ticks", type=int, default=1, help="Simulation ticks to run")
    parser.add_argument("--dt", type=float, default=0.1, help="Seconds per simulation tick")
    parser.add_argument("--say", action="append", default=[], help="Queue avatar chat on channel 0")
    parser.add_argument(
        "--touch",
        action="store_true",
        help="Queue one touch_start event from the default avatar",
    )
    parser.add_argument("--avatar", default="Offline User", help="Default avatar name")
    parser.add_argument("--examples", action="store_true", help="Check all scripts under examples/")
    args = parser.parse_args(argv)

    if args.examples:
        from .check_examples import main as check_examples_main

        check_args = ["examples"]
        if not args.check:
            check_args.extend(["--run", "--allow-runtime-failures"])
        return check_examples_main(check_args)

    if not args.script:
        parser.error("script is required unless --examples is used")

    script_path = Path(args.script)
    try:
        source = script_path.read_text(encoding="utf-8")
    except OSError as e:
        parser.error(str(e))

    if args.check:
        ast = parse_lsl(source)
        print(
            f"OK: parsed {script_path} "
            f"({len(ast.globals)} globals/functions, {len(ast.states)} states)"
        )
        return 0

    runtime = build_runtime(
        source,
        script_name=script_path.name,
        avatar_name=args.avatar,
    )

    runtime.tick()
    for message in args.say:
        runtime.say(message)
    if args.touch:
        runtime.touch()
    if args.ticks > 0:
        runtime.tick(args.ticks, args.dt)

    print(
        f"OK: ran {script_path} for {args.ticks + 1} ticks; "
        f"state={runtime.script.current_state}; queued_events={len(runtime.script.event_queue)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
