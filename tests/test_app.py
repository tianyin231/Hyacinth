import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMainWindow
from pytestqt.qtbot import QtBot


def test_create_main_window_uses_product_identity(qtbot: QtBot) -> None:
    try:
        from hyacinth.app import create_main_window
    except ModuleNotFoundError:
        pytest.fail("hyacinth.app.create_main_window is not implemented")

    window = create_main_window()
    qtbot.addWidget(window)

    assert isinstance(window, QMainWindow)
    assert window.windowTitle() == "风信子"
    assert window.objectName() == "main-window"


def test_main_runs_qt_event_loop(qapp: QApplication) -> None:
    try:
        from hyacinth.__main__ import main
    except ModuleNotFoundError:
        pytest.fail("hyacinth.__main__.main is not implemented")

    QTimer.singleShot(0, qapp.quit)

    assert main([]) == 0
