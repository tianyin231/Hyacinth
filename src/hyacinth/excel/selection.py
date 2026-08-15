from collections.abc import Callable

from hyacinth.excel.com_engine import ComExcelEngine, is_excel_com_available
from hyacinth.excel.python_engine import PythonExcelEngine


def select_engine[EngineT](
    *,
    com_engine: EngineT,
    python_engine: EngineT,
    is_com_available: Callable[[], bool],
) -> EngineT:
    if is_com_available():
        return com_engine
    return python_engine


def create_default_engine(
    is_com_available: Callable[[], bool] = is_excel_com_available,
) -> ComExcelEngine | PythonExcelEngine:
    com_engine: ComExcelEngine | PythonExcelEngine = ComExcelEngine()
    python_engine: ComExcelEngine | PythonExcelEngine = PythonExcelEngine()
    return select_engine(
        com_engine=com_engine,
        python_engine=python_engine,
        is_com_available=is_com_available,
    )
