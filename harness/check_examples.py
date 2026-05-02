from __future__ import annotations

import argparse
import contextlib
import io
from dataclasses import dataclass
from pathlib import Path

from .runtime import build_runtime, parse_lsl


@dataclass
class ExampleResult:
    path: Path
    parse_ok: bool
    run_ok: bool | None = None
    error: str = ""


def check_example(
    path: Path,
    *,
    run: bool = False,
    ticks: int = 3,
    dt: float = 0.1,
    verbose: bool = False,
) -> ExampleResult:
    source = path.read_text(encoding="utf-8")
    try:
        parse_lsl(source)
    except Exception as e:
        return ExampleResult(path=path, parse_ok=False, run_ok=False if run else None, error=str(e))

    if not run:
        return ExampleResult(path=path, parse_ok=True)

    try:
        output = None if verbose else io.StringIO()
        with contextlib.redirect_stdout(output):
            runtime = build_runtime(source, script_name=path.name)
            runtime.tick(ticks, dt)
    except Exception as e:
        return ExampleResult(path=path, parse_ok=True, run_ok=False, error=str(e))

    return ExampleResult(path=path, parse_ok=True, run_ok=True)


def find_examples(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.lsl") if path.is_file())


def format_results(results: list[ExampleResult], *, run: bool = False) -> str:
    name_width = max([len("script"), *(len(str(r.path)) for r in results)])
    headers = ["script".ljust(name_width), "parse"]
    if run:
        headers.append("run")
    headers.append("error")
    lines = ["  ".join(headers)]
    separator = ["-" * name_width, "-----"]
    if run:
        separator.append("---")
    separator.append("-----")
    lines.append("  ".join(separator))

    for result in results:
        fields = [
            str(result.path).ljust(name_width),
            "ok" if result.parse_ok else "fail",
        ]
        if run:
            fields.append("ok" if result.run_ok else "fail")
        fields.append(result.error)
        lines.append("  ".join(fields).rstrip())
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lsl-check-examples",
        description="Parse and optionally smoke-run the example LSL scripts.",
    )
    parser.add_argument(
        "root",
        nargs="?",
        default="examples",
        help="Directory containing .lsl examples",
    )
    parser.add_argument("--run", action="store_true", help="Run state_entry for each parsed script")
    parser.add_argument("--ticks", type=int, default=3, help="Simulation ticks for --run")
    parser.add_argument("--dt", type=float, default=0.1, help="Seconds per simulation tick")
    parser.add_argument("--verbose", action="store_true", help="Show script output during --run")
    parser.add_argument(
        "--allow-runtime-failures",
        action="store_true",
        help="Exit successfully when parse passes but runtime smoke tests fail",
    )
    args = parser.parse_args(argv)

    root = Path(args.root)
    examples = find_examples(root)
    if not examples:
        parser.error(f"no .lsl files found under {root}")

    results = [
        check_example(path, run=args.run, ticks=args.ticks, dt=args.dt, verbose=args.verbose)
        for path in examples
    ]
    print(format_results(results, run=args.run))

    parse_failed = any(not result.parse_ok for result in results)
    run_failed = args.run and any(result.run_ok is False for result in results)
    if parse_failed or (run_failed and not args.allow_runtime_failures):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
