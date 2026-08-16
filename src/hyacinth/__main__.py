import multiprocessing
import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from hyacinth.app import create_main_window
from hyacinth.app_icon import application_icon
from hyacinth.diagnostics import install_crash_diagnostics
from hyacinth.excel.com_worker import COM_WORKER_FLAG


def main(argv: Sequence[str] | None = None) -> int:
    # 冻结 exe 中 multiprocessing spawn 子进程会带着 --multiprocessing-fork
    # 重新进入本入口；freeze_support 必须先于任何 Qt 初始化接管该分支。
    multiprocessing.freeze_support()
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == [COM_WORKER_FLAG]:
        from hyacinth.excel.com_worker import main as com_worker_main

        return com_worker_main(arguments[1:])
    install_crash_diagnostics()
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication(list(argv) if argv is not None else sys.argv)
    app.setWindowIcon(application_icon())
    window = create_main_window()
    window.show()
    try:
        return app.exec()
    finally:
        window.close()


if __name__ == "__main__":
    raise SystemExit(main())
