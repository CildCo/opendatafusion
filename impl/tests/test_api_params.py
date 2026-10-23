import pytest

from odf.apistudio.params import (ParamError, coerce_params, sample_values,
                                  validate_param_defs)


def test_validate_defs_rejects_duplicate_and_bad_name():
    with pytest.raises(ParamError):
        validate_param_defs([{"name": "a", "type": "string"},
                             {"name": "a", "type": "number"}])
    with pytest.raises(ParamError):
        validate_param_defs([{"name": "bad-name", "type": "string"}])


def test_validate_defs_requires_known_type():
    with pytest.raises(ParamError):
        validate_param_defs([{"name": "a", "type": "blob"}])


def test_required_parameter_missing():
    defs = [{"name": "start", "type": "date", "required": True}]
    with pytest.raises(ParamError) as e:
        coerce_params(defs, {})
    assert e.value.parameter == "start"


def test_coercion_and_defaults():
    defs = [
        {"name": "n", "type": "number", "required": True},
        {"name": "ok", "type": "bool", "default": False},
        {"name": "q", "type": "string", "default": "all"},
    ]
    out = coerce_params(defs, {"n": "3.5"})
    assert out == {"n": 3.5, "ok": False, "q": "all"}


def test_bad_number_is_a_parameter_error():
    defs = [{"name": "n", "type": "number", "required": True}]
    with pytest.raises(ParamError) as e:
        coerce_params(defs, {"n": "abc"})
    assert e.value.parameter == "n"


def test_array_parameter_is_coerced_elementwise():
    defs = [{"name": "cities", "type": "string"}]
    assert coerce_params(defs, {"cities": ["a", "b"]}) == {
        "cities": ["a", "b"]}


def test_sample_values_are_typed():
    defs = [
        {"name": "s", "type": "string"},
        {"name": "n", "type": "number"},
        {"name": "d", "type": "date"},
        {"name": "b", "type": "bool"},
    ]
    out = sample_values(defs)
    assert isinstance(out["s"], str)
    assert isinstance(out["n"], (int, float))
    assert isinstance(out["d"], str)
    assert isinstance(out["b"], bool)


def test_invalid_date_is_a_parameter_error():
    defs = [{"name": "d", "type": "date"}]
    with pytest.raises(ParamError) as e:
        coerce_params(defs, {"d": "not-a-date"})
    assert e.value.parameter == "d"


def test_in_list_is_capped():
    import pytest
    with pytest.raises(ParamError):
        coerce_params([{"name": "ids", "type": "number"}],
                      {"ids": list(range(101))})
