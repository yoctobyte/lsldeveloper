from pathlib import Path

from harness.check_examples import check_example, find_examples, format_results, main
from harness.runtime import build_runtime


def test_all_examples_parse():
    examples = find_examples(Path("examples"))

    assert examples
    results = [check_example(path) for path in examples]

    assert all(result.parse_ok for result in results), format_results(results)


def test_example_runtime_smoke_accepts_stubbed_api(capsys):
    result = check_example(Path("examples/unsupported_missing_api.lsl"), run=True)

    assert result.parse_ok
    assert result.run_ok is True

    source = Path("examples/unsupported_missing_api.lsl").read_text(encoding="utf-8")
    runtime = build_runtime(source)
    runtime.tick()

    assert "STUB llTeleportAgent: not implemented" in capsys.readouterr().out


def test_examples_cli_allows_expected_runtime_failures(capsys):
    assert main(["examples", "--run", "--allow-runtime-failures"]) == 0

    out = capsys.readouterr().out
    assert "unsupported_missing_api.lsl" in out
    assert "fail" not in out
