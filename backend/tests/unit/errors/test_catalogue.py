from pydantic import BaseModel

from infrahub.errors.catalogue import CATALOGUE, EXCEPTION_TO_CODE


def test_catalogue_is_not_empty() -> None:
    assert len(CATALOGUE) > 0


def test_every_code_has_a_pydantic_payload_model() -> None:
    for code, entry in CATALOGUE.items():
        assert issubclass(entry.payload_model, BaseModel), code


def test_payload_models_forbid_extra_fields() -> None:
    for code, entry in CATALOGUE.items():
        config = entry.payload_model.model_config
        assert config.get("extra") == "forbid", code


def test_undefined_error_is_present_with_empty_payload_and_no_exception() -> None:
    entry = CATALOGUE["UNDEFINED_ERROR"]
    assert entry.exception_class is None
    assert entry.http_status == 500
    assert entry.payload_model.model_fields == {}


def test_exception_to_code_reverse_map_covers_every_class_routed_exception() -> None:
    # Every entry with a single exception_class (i.e. excluding AuthorizationError's split routing
    # and UNDEFINED_ERROR's None) should be reachable via the reverse map.
    for code, entry in CATALOGUE.items():
        if entry.exception_class is None:
            continue
        if code in {"AUTHENTICATION_REQUIRED", "TOKEN_EXPIRED"}:
            assert entry.exception_class not in EXCEPTION_TO_CODE, code
            continue
        assert EXCEPTION_TO_CODE[entry.exception_class] == code
