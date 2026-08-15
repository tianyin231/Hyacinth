import pytest


class FakeExcelApplication:
    Version = "16.0"

    def __init__(self) -> None:
        self.quit_called = False

    def Quit(self) -> None:
        self.quit_called = True


def test_com_probe_closes_excel_after_success() -> None:
    try:
        from hyacinth.excel.com_engine import is_excel_com_available
    except ModuleNotFoundError:
        pytest.fail("hyacinth.excel.com_engine.is_excel_com_available is not implemented")

    app = FakeExcelApplication()

    assert is_excel_com_available(lambda _: app) is True
    assert app.quit_called is True


def test_com_probe_reports_startup_failure() -> None:
    try:
        from hyacinth.excel.com_engine import is_excel_com_available
    except ModuleNotFoundError:
        pytest.fail("hyacinth.excel.com_engine.is_excel_com_available is not implemented")

    def fail_to_start(_: str) -> FakeExcelApplication:
        raise RuntimeError("Excel is unavailable")

    assert is_excel_com_available(fail_to_start) is False
