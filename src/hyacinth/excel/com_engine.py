import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol, cast

from win32com.client import DispatchEx  # type: ignore[import-untyped]

from hyacinth.excel.contracts import (
    ConversionProgress,
    ConversionResult,
    EngineName,
    capabilities_for,
)


class ExcelApplication(Protocol):
    Version: str

    def Quit(self) -> None: ...


ExcelDispatch = Callable[[str], ExcelApplication]


def _dispatch_excel(program_id: str) -> ExcelApplication:
    return cast(ExcelApplication, DispatchEx(program_id))


def is_excel_com_available(dispatch: ExcelDispatch | None = None) -> bool:
    if dispatch is None:
        completed = _run_worker("--probe")
        return completed.returncode == 0

    app: ExcelApplication | None = None
    try:
        app = dispatch("Excel.Application")
        _ = app.Version
    except Exception:
        return False
    finally:
        if app is not None:
            app.Quit()
    return True


class ComExcelEngine:
    name = EngineName.COM
    capabilities = capabilities_for(name)

    def convert_xls_to_xlsx(
        self,
        source: Path,
        destination: Path,
        progress: ConversionProgress | None = None,
    ) -> ConversionResult:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix="hyacinth-com-") as temporary_directory:
            safe_source = Path(temporary_directory) / source.name
            shutil.copy2(source, safe_source)
            completed = _run_worker(str(safe_source), str(destination.resolve()))
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "Excel COM conversion failed")

        return ConversionResult(engine=self.name, output_path=destination)


def _run_worker(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "hyacinth.excel.com_worker", *arguments],
        capture_output=True,
        text=True,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
