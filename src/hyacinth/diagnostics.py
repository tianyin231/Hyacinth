import faulthandler
import os
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

_crash_log = None
_original_excepthook = sys.excepthook


def default_crash_log_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    root = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    return root / "Hyacinth" / "logs" / "crash.log"


def install_crash_diagnostics(path: Path | None = None) -> Path:
    global _crash_log
    log_path = path or default_crash_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _crash_log = log_path.open("a", encoding="utf-8", buffering=1)
    _crash_log.write(f"\n=== 风信子启动 {datetime.now(UTC).isoformat()} ===\n")
    faulthandler.enable(file=_crash_log, all_threads=True)

    def log_uncaught_exception(
        exception_type: type[BaseException],
        exception: BaseException,
        exception_traceback: TracebackType | None,
    ) -> None:
        assert _crash_log is not None
        traceback.print_exception(
            exception_type,
            exception,
            exception_traceback,
            file=_crash_log,
        )
        _original_excepthook(exception_type, exception, exception_traceback)

    sys.excepthook = log_uncaught_exception
    return log_path
