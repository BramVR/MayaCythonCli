from __future__ import annotations

from dataclasses import dataclass


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

    def __str__(self) -> str:
        return self.message
