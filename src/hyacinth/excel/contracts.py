from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol


class EngineName(StrEnum):
    COM = "com"
    PYTHON = "python"


class ConversionWarning(StrEnum):
    COMPLEX_FORMATTING_MAY_BE_LOST = "complex-formatting-may-be-lost"
    XLS_FORMULAS_MAY_BECOME_CACHED_VALUES = "xls-formulas-may-become-cached-values"


@dataclass(frozen=True)
class EngineCapabilities:
    recalculates_formulas: bool
    preserves_complex_formatting: bool
    limitations: tuple[ConversionWarning, ...]


@dataclass(frozen=True)
class ConversionResult:
    engine: EngineName
    output_path: Path
    warnings: tuple[ConversionWarning, ...] = ()


class ConversionProgress(Protocol):
    def report_progress(self, progress: float | None, message: str = "") -> None: ...

    def check_cancelled(self) -> None: ...


def capabilities_for(engine: EngineName) -> EngineCapabilities:
    if engine is EngineName.COM:
        return EngineCapabilities(
            recalculates_formulas=True,
            preserves_complex_formatting=True,
            limitations=(),
        )
    return EngineCapabilities(
        recalculates_formulas=False,
        preserves_complex_formatting=False,
        limitations=(
            ConversionWarning.COMPLEX_FORMATTING_MAY_BE_LOST,
            ConversionWarning.XLS_FORMULAS_MAY_BECOME_CACHED_VALUES,
        ),
    )
