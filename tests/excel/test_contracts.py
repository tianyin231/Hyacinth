import pytest


def test_capabilities_describe_com_and_python_boundaries() -> None:
    try:
        from hyacinth.excel.contracts import EngineName, capabilities_for
    except ModuleNotFoundError:
        pytest.fail("hyacinth.excel.contracts is not implemented")

    com = capabilities_for(EngineName.COM)
    python = capabilities_for(EngineName.PYTHON)

    assert com.recalculates_formulas is True
    assert com.preserves_complex_formatting is True
    assert com.limitations == ()
    assert python.recalculates_formulas is False
    assert python.preserves_complex_formatting is False
    assert {warning.value for warning in python.limitations} == {
        "complex-formatting-may-be-lost",
        "xls-formulas-may-become-cached-values",
    }
