import pytest

from api_contract.spec_registry import get_spec, register_spec


def test_register_then_get_roundtrip():
    spec = {"openapi": "3.0.0", "info": {"title": "A", "version": "1"}}

    spec_id = register_spec(spec)

    assert get_spec(spec_id) == spec


def test_registering_the_same_spec_content_twice_reuses_the_id():
    spec = {"openapi": "3.0.0", "info": {"title": "B", "version": "1"}}

    first = register_spec(spec)
    second = register_spec(dict(spec))

    assert first == second


def test_registering_different_spec_content_yields_different_ids():
    first_id = register_spec({"openapi": "3.0.0", "info": {"title": "C", "version": "1"}})
    second_id = register_spec({"openapi": "3.0.0", "info": {"title": "D", "version": "1"}})

    assert first_id != second_id


def test_get_spec_raises_for_unknown_id():
    with pytest.raises(ValueError, match="Unknown spec_id"):
        get_spec("does-not-exist")
