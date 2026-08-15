import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from hyacinth.app import create_main_window


def main(argv: Sequence[str] | None = None) -> int:
    app = QApplication.instance() or QApplication(list(argv) if argv is not None else sys.argv)
    window = create_main_window()
    window.show()
    try:
        return app.exec()
    finally:
        window.close()


if __name__ == "__main__":
    raise SystemExit(main())
