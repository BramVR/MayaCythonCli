from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

USAGE_ERROR = 2
DEPENDENCY_ERROR = 3
BUILD_ERROR = 4
SMOKE_ERROR = 5
ASSEMBLE_ERROR = 6
INTERRUPTED_ERROR = 130


@dataclass(slots=True)
class CliError(Exception):
    message: str
    exit_code: int
    error_code: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message
