"""Shared setup: import the CLIs by path and keep every test off the network."""

from __future__ import annotations

import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "animated-svg" / "scripts"
for path in (SCRIPTS, ROOT / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError("network access is blocked in tests")

    monkeypatch.setattr(socket.socket, "connect", refuse)
