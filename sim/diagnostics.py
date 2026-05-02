from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class Diagnostic:
    severity: str
    phase: str
    message: str
    object_name: str = ""
    script_name: str = ""
    line: Optional[int] = None
    column: Optional[int] = None

    @property
    def location(self) -> str:
        if self.line is None:
            return ""
        if self.column is None:
            return str(self.line)
        return f"{self.line}:{self.column}"

    def label(self) -> str:
        owner = "/".join(part for part in [self.object_name, self.script_name] if part)
        prefix = f"{owner} " if owner else ""
        location = f"{self.location} " if self.location else ""
        return f"{prefix}{self.phase} {location}{self.message}".strip()


def diagnostic_from_exception(
    exc: Exception,
    *,
    phase: str,
    object_name: str = "",
    script_name: str = "",
    severity: str = "error",
) -> Diagnostic:
    message = str(exc) or exc.__class__.__name__
    line = None
    column = None
    match = re.search(r"line (\d+), column (\d+)", message)
    if match:
        line = int(match.group(1))
        column = int(match.group(2))
    return Diagnostic(
        severity=severity,
        phase=phase,
        message=message,
        object_name=object_name,
        script_name=script_name,
        line=line,
        column=column,
    )
