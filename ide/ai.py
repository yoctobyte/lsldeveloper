from __future__ import annotations

import json
import os
import stat
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_MODEL = "gpt-5.2"
SETTINGS_PATH = Path.home() / ".config" / "lsldeveloper" / "settings.json"


@dataclass
class AiSettings:
    api_key: str = ""
    model: str = DEFAULT_MODEL

    @classmethod
    def load(cls, path: Path = SETTINGS_PATH) -> "AiSettings":
        if not path.exists():
            return cls(api_key=os.environ.get("OPENAI_API_KEY", ""))
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            api_key=str(data.get("api_key") or os.environ.get("OPENAI_API_KEY", "")),
            model=str(data.get("model") or DEFAULT_MODEL),
        )

    def save(self, path: Path = SETTINGS_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"api_key": self.api_key, "model": self.model}, indent=2), encoding="utf-8")
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


@dataclass
class AiEdit:
    object_name: str
    script_name: str
    source: str


@dataclass
class AiResult:
    answer: str
    edits: list[AiEdit] = field(default_factory=list)


class AiError(RuntimeError):
    pass


def build_project_prompt(project, question: str) -> str:
    scripts = []
    for obj in project.objects:
        for script in obj.scripts:
            scripts.append(
                {
                    "object": obj.name,
                    "script": script.name,
                    "source": script.source,
                }
            )

    payload = {
        "question": question,
        "project": {
            "objects": [
                {
                    "name": obj.name,
                    "description": obj.description,
                    "position": [obj.position.x, obj.position.y, obj.position.z],
                    "scripts": [script.name for script in obj.scripts],
                }
                for obj in project.objects
            ],
            "scripts": scripts,
        },
    }
    return (
        "You are helping edit an offline LSL project. The project contains objects, and each object contains scripts.\n"
        "Answer the user's question and freely edit scripts when useful.\n"
        "Only edit scripts that are present in the supplied project. Return full replacement source for edited scripts.\n"
        "Do not invent files, Python code, or simulator internals.\n"
        "Return JSON only with this shape:\n"
        '{"answer":"short explanation","edits":[{"object":"Object name","script":"script.lsl","source":"full LSL source"}]}\n\n'
        f"{json.dumps(payload, indent=2)}"
    )


def parse_ai_result(text: str) -> AiResult:
    data = json.loads(_extract_json_object(text))
    edits = [
        AiEdit(
            object_name=str(item.get("object", "")),
            script_name=str(item.get("script", "")),
            source=str(item.get("source", "")),
        )
        for item in data.get("edits", [])
    ]
    return AiResult(answer=str(data.get("answer", "")), edits=edits)


def _extract_json_object(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1]
    raise AiError("AI response did not contain a JSON object")


def apply_ai_edits(project, edits: list[AiEdit]) -> list[str]:
    changed = []
    for edit in edits:
        for obj in project.objects:
            if obj.name != edit.object_name:
                continue
            for script in obj.scripts:
                if script.name == edit.script_name:
                    script.source = edit.source.rstrip() + "\n"
                    script.dirty = True
                    changed.append(f"{obj.name}/{script.name}")
                    break
            break
    return changed


class OpenAiClient:
    def __init__(self, settings: AiSettings):
        self.settings = settings

    def ask_project(self, project, question: str) -> AiResult:
        if not self.settings.api_key:
            raise AiError("OpenAI API key is not configured")
        prompt = build_project_prompt(project, question)
        response_text = self._create_response(prompt)
        return parse_ai_result(response_text)

    def _create_response(self, prompt: str) -> str:
        body = {
            "model": self.settings.model,
            "input": prompt,
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise AiError(f"OpenAI API error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise AiError(f"OpenAI API request failed: {exc.reason}") from exc

        return extract_response_text(payload)


def extract_response_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    parts = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if isinstance(content.get("text"), str):
                parts.append(content["text"])
    if parts:
        return "\n".join(parts)
    raise AiError("OpenAI response did not include output text")
