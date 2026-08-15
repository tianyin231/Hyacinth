from pathlib import Path

from pytest import MonkeyPatch


def test_default_crash_log_uses_local_application_data(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    from hyacinth.diagnostics import default_crash_log_path

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert default_crash_log_path() == tmp_path / "Hyacinth" / "logs" / "crash.log"
