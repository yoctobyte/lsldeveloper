from ide.ai import AiEdit, apply_ai_edits, build_project_prompt, extract_response_text, parse_ai_result
from ide.project import IdeProject, ProjectObject, ProjectScript


def test_ai_result_parses_fenced_json_and_applies_script_edits(tmp_path):
    project = IdeProject(
        tmp_path,
        [
            ProjectObject(
                "Door",
                scripts=[ProjectScript("door.lsl", 'default { state_entry() { llOwnerSay("old"); } }\n')],
            )
        ],
    )

    result = parse_ai_result(
        """
```json
{
  "answer": "Updated the greeting.",
  "edits": [
    {
      "object": "Door",
      "script": "door.lsl",
      "source": "default {\\n    state_entry() { llOwnerSay(\\"new\\"); }\\n}\\n"
    }
  ]
}
```
"""
    )

    changed = apply_ai_edits(project, result.edits)

    assert result.answer == "Updated the greeting."
    assert changed == ["Door/door.lsl"]
    assert 'llOwnerSay("new")' in project.objects[0].scripts[0].source


def test_ai_prompt_contains_project_scripts(tmp_path):
    project = IdeProject(
        tmp_path,
        [ProjectObject("Box", scripts=[ProjectScript("main.lsl", "default {}\n")])],
    )

    prompt = build_project_prompt(project, "What does this do?")

    assert '"object": "Box"' in prompt
    assert '"script": "main.lsl"' in prompt
    assert "Return JSON only" in prompt


def test_extract_response_text_supports_output_text_and_output_blocks():
    assert extract_response_text({"output_text": "hello"}) == "hello"
    assert (
        extract_response_text(
            {
                "output": [
                    {
                        "content": [
                            {"text": "part 1"},
                            {"text": "part 2"},
                        ]
                    }
                ]
            }
        )
        == "part 1\npart 2"
    )


def test_unknown_ai_edit_is_ignored(tmp_path):
    project = IdeProject(tmp_path, [ProjectObject("Box", scripts=[ProjectScript("main.lsl", "default {}\n")])])

    changed = apply_ai_edits(project, [AiEdit("Other", "main.lsl", "changed")])

    assert changed == []
    assert project.objects[0].scripts[0].source == "default {}\n"
