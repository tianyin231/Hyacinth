import sys
from collections.abc import Sequence

import pytest

from hyacinth.__main__ import main
from hyacinth.excel.com_engine import _worker_command
from hyacinth.excel.com_worker import COM_WORKER_FLAG


def test_worker_command_uses_module_entry_in_source_build() -> None:
    assert _worker_command("--probe") == [
        sys.executable,
        "-m",
        "hyacinth.excel.com_worker",
        "--probe",
    ]


def test_worker_command_reuses_frozen_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    command = _worker_command("a.xls", "b.xlsx")
    assert command == [sys.executable, COM_WORKER_FLAG, "a.xls", "b.xlsx"]
    assert "-m" not in command


def test_main_dispatches_com_worker_flag_without_qt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import hyacinth.excel.com_worker as com_worker

    seen: list[list[str]] = []

    def fake_main(arguments: Sequence[str] | None = None) -> int:
        seen.append(list(arguments or ()))
        return 7

    monkeypatch.setattr(com_worker, "main", fake_main)
    assert main([COM_WORKER_FLAG, "--probe"]) == 7
    assert seen == [["--probe"]]
