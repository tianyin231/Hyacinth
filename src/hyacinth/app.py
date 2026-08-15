from PySide6.QtWidgets import QMainWindow


def create_main_window() -> QMainWindow:
    window = QMainWindow()
    window.setObjectName("main-window")
    window.setWindowTitle("风信子")
    return window
