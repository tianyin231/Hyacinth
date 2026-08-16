import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pythoncom  # type: ignore[import-untyped]
from win32com.client import DispatchEx  # type: ignore[import-untyped]

# PyInstaller 冻结后无法用 `python -m`，主 exe 以该参数转投 COM 子进程入口。
COM_WORKER_FLAG = "--hyacinth-com-worker"


def main(arguments: Sequence[str] | None = None) -> int:
    args = list(arguments if arguments is not None else sys.argv[1:])
    if args == ["--probe"]:
        return _probe_excel()
    if len(args) == 2:
        _convert_xls_to_xlsx(Path(args[0]), Path(args[1]))
        return 0
    return 2


def _probe_excel() -> int:
    pythoncom.CoInitialize()
    app: Any | None = None
    try:
        app = DispatchEx("Excel.Application")
        _ = app.Version
        return 0
    except Exception:
        return 1
    finally:
        if app is not None:
            app.Quit()
            app = None
        pythoncom.CoUninitialize()


def _convert_xls_to_xlsx(source: Path, destination: Path) -> None:
    pythoncom.CoInitialize()
    app: Any | None = None
    workbook: Any | None = None
    try:
        app = DispatchEx("Excel.Application")
        app.Visible = False
        app.DisplayAlerts = False
        workbook = app.Workbooks.Open(str(source), ReadOnly=True)
        app.CalculateFull()
        workbook.SaveAs(str(destination), FileFormat=51)
    finally:
        if workbook is not None:
            workbook.Close(SaveChanges=False)
            workbook = None
        if app is not None:
            app.Quit()
            app = None
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    raise SystemExit(main())
