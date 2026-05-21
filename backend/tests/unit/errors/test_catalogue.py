import pytest
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from infrahub.errors.catalogue import CATALOGUE, CatalogueEntry


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


def test_adopted_exception_classes_carry_catalogue_code() -> None:
    for code, entry in CATALOGUE.items():
        exception_class = entry.exception_class
        if exception_class is None:
            continue
        if code in {"AUTHENTICATION_REQUIRED", "TOKEN_EXPIRED"}:
            # Split at the formatter; the exception itself has no single code.
            continue
        catalogue_code = getattr(exception_class, "CATALOGUE_CODE", None)
        assert catalogue_code == code, (code, catalogue_code)


def test_catalogue_codes_match_entry_codes() -> None:
    for code, entry in CATALOGUE.items():
        assert entry.code == code


def test_catalogue_entry_is_frozen() -> None:
    entry = CATALOGUE["NODE_NOT_FOUND"]
    assert isinstance(entry, CatalogueEntry)
    with pytest.raises(PydanticValidationError, match=r"frozen"):
        entry.code = "X"
