import json
from pathlib import Path

import pytest

from infrahub.errors.catalogue import CATALOGUE
from infrahub.errors.export import CATALOGUE_VERSION, export_catalogue, write_catalogue


def test_export_top_level_shape() -> None:
    payload = export_catalogue()
    assert payload["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert payload["infrahub_catalogue_version"] == CATALOGUE_VERSION
    assert "generated_at" in payload
    assert set(payload["codes"]) == set(CATALOGUE)


def test_export_preserves_catalogue_order() -> None:
    payload = export_catalogue()
    assert list(payload["codes"]) == list(CATALOGUE)


def test_every_entry_has_required_fields() -> None:
    payload = export_catalogue()
    required_top_level = {"description", "stability", "http_status", "data_schema"}
    for code, entry in payload["codes"].items():
        assert required_top_level.issubset(entry), code
        data_schema = entry["data_schema"]
        assert data_schema.get("type") == "object", code
        assert data_schema.get("additionalProperties") is False, code
        assert "properties" in data_schema, code
        assert "required" in data_schema, code


@pytest.mark.parametrize("code", list(CATALOGUE.keys()), ids=list(CATALOGUE.keys()))
def test_entry_matches_catalogue_metadata(code: str) -> None:
    payload = export_catalogue()
    entry = payload["codes"][code]
    catalogue_entry = CATALOGUE[code]
    assert entry["description"] == catalogue_entry.description
    assert entry["stability"] == catalogue_entry.stability
    assert entry["http_status"] == catalogue_entry.http_status
    assert entry["data_schema"]["title"] == catalogue_entry.payload_model.__name__


def test_write_catalogue_round_trip(tmp_path: Path) -> None:
    destination = tmp_path / "error-catalogue.json"
    write_catalogue(destination)
    loaded = json.loads(destination.read_text(encoding="utf-8"))
    assert set(loaded["codes"]) == set(CATALOGUE)
    assert loaded["infrahub_catalogue_version"] == CATALOGUE_VERSION
