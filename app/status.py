"""Application status types shared by the controller and the UI."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StackStatus(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    READY = "ready"
    UNHEALTHY = "unhealthy"
    ERROR = "error"


@dataclass(frozen=True)
class StatusReport:
    status: StackStatus
    detail: str = ""
