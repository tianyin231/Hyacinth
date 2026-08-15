import pytest


def test_select_engine_prefers_com_when_available() -> None:
    try:
        from hyacinth.excel.selection import select_engine
    except ModuleNotFoundError:
        pytest.fail("hyacinth.excel.selection.select_engine is not implemented")

    selected = select_engine(
        com_engine="com",
        python_engine="python",
        is_com_available=lambda: True,
    )

    assert selected == "com"


def test_select_engine_falls_back_to_python() -> None:
    try:
        from hyacinth.excel.selection import select_engine
    except ModuleNotFoundError:
        pytest.fail("hyacinth.excel.selection.select_engine is not implemented")

    selected = select_engine(
        com_engine="com",
        python_engine="python",
        is_com_available=lambda: False,
    )

    assert selected == "python"


def test_create_default_engine_uses_probe_result() -> None:
    try:
        from hyacinth.excel.com_engine import ComExcelEngine
        from hyacinth.excel.python_engine import PythonExcelEngine
        from hyacinth.excel.selection import create_default_engine
    except ImportError:
        pytest.fail("hyacinth.excel.selection.create_default_engine is not implemented")

    assert isinstance(create_default_engine(lambda: True), ComExcelEngine)
    assert isinstance(create_default_engine(lambda: False), PythonExcelEngine)
