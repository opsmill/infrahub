"""Unit tests for infrahub.ai.extraction module."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.ai.extraction import (
    ExtractableAttribute,
    ExtractableRelationship,
    _FILE_OBJECT_BASE_ATTRIBUTES,
    _NON_EXTRACTABLE_KINDS,
    build_extraction_prompt,
    get_extractable_attributes,
    get_extractable_relationships,
    parse_extraction_response,
)


# ---------------------------------------------------------------------------
# Minimal stand-ins for the SDK schema types used in extraction.py
# ---------------------------------------------------------------------------


@dataclass
class _FakeAttributeSchema:
    name: str
    kind: str
    description: str | None = None
    optional: bool = True
    read_only: bool = False
    choices: list[dict[str, Any]] | None = None


@dataclass
class _FakeRelationshipSchema:
    name: str
    peer: str
    kind: str = "Attribute"
    cardinality: str = "one"
    description: str | None = None
    read_only: bool = False
    optional: bool = True


@dataclass
class _FakeNodeSchema:
    attributes: list[_FakeAttributeSchema]
    relationships: list[_FakeRelationshipSchema] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.relationships is None:
            self.relationships = []


# ---------------------------------------------------------------------------
# get_extractable_attributes
# ---------------------------------------------------------------------------


def test_get_extractable_attributes_filters_file_object_base() -> None:
    schema = _FakeNodeSchema(
        attributes=[
            _FakeAttributeSchema(name="file_name", kind="Text"),
            _FakeAttributeSchema(name="checksum", kind="Text"),
            _FakeAttributeSchema(name="storage_id", kind="Text"),
            _FakeAttributeSchema(name="file_size", kind="Number"),
            _FakeAttributeSchema(name="file_type", kind="Text"),
            _FakeAttributeSchema(name="description", kind="Text"),
        ]
    )
    result = get_extractable_attributes(schema)  # type: ignore[arg-type]
    names = [a.name for a in result]
    assert "description" in names
    for base in _FILE_OBJECT_BASE_ATTRIBUTES:
        assert base not in names


def test_get_extractable_attributes_filters_non_extractable_kinds() -> None:
    schema = _FakeNodeSchema(
        attributes=[
            _FakeAttributeSchema(name="password_field", kind="Password"),
            _FakeAttributeSchema(name="pool_field", kind="NumberPool"),
            _FakeAttributeSchema(name="note", kind="Text"),
        ]
    )
    result = get_extractable_attributes(schema)  # type: ignore[arg-type]
    names = [a.name for a in result]
    assert "note" in names
    for kind in _NON_EXTRACTABLE_KINDS:
        bad_names = [a.name for a in result if a.kind == kind]
        assert not bad_names, f"Non-extractable kind {kind!r} slipped through: {bad_names}"


def test_get_extractable_attributes_filters_read_only() -> None:
    schema = _FakeNodeSchema(
        attributes=[
            _FakeAttributeSchema(name="editable", kind="Text", read_only=False),
            _FakeAttributeSchema(name="immutable", kind="Text", read_only=True),
        ]
    )
    result = get_extractable_attributes(schema)  # type: ignore[arg-type]
    names = [a.name for a in result]
    assert "editable" in names
    assert "immutable" not in names


def test_get_extractable_attributes_returns_dropdown_choices() -> None:
    schema = _FakeNodeSchema(
        attributes=[
            _FakeAttributeSchema(
                name="status",
                kind="Dropdown",
                choices=[{"value": "active"}, {"value": "inactive"}],
            )
        ]
    )
    result = get_extractable_attributes(schema)  # type: ignore[arg-type]
    assert len(result) == 1
    assert result[0].choices == ["active", "inactive"]


# ---------------------------------------------------------------------------
# build_extraction_prompt
# ---------------------------------------------------------------------------


def test_build_extraction_prompt_includes_fields() -> None:
    attributes = [
        ExtractableAttribute(name="start_date", kind="DateTime", description="Contract start date"),
        ExtractableAttribute(name="is_active", kind="Checkbox", description=None),
    ]
    prompt = build_extraction_prompt(attributes=attributes, file_name="contract.pdf", file_type="application/pdf")

    assert "start_date" in prompt
    assert "Contract start date" in prompt
    assert "is_active" in prompt
    assert "true or false" in prompt
    assert "contract.pdf" in prompt
    assert "application/pdf" in prompt
    assert "JSON" in prompt


def test_build_extraction_prompt_dropdown_choices() -> None:
    attributes = [
        ExtractableAttribute(name="status", kind="Dropdown", description=None, choices=["active", "inactive"])
    ]
    prompt = build_extraction_prompt(attributes=attributes, file_name="f.txt", file_type="text/plain")
    assert "active" in prompt
    assert "inactive" in prompt


# ---------------------------------------------------------------------------
# parse_extraction_response
# ---------------------------------------------------------------------------


def test_parse_extraction_response_happy_path() -> None:
    attributes = [
        ExtractableAttribute(name="start_date", kind="DateTime", description=None),
        ExtractableAttribute(name="end_date", kind="DateTime", description=None),
    ]
    response = json.dumps({"start_date": "2026-01-01", "end_date": "2026-12-31"})
    result = parse_extraction_response(response_text=response, attributes=attributes)
    assert result == {"start_date": "2026-01-01", "end_date": "2026-12-31"}


def test_parse_extraction_response_drops_null_values() -> None:
    attributes = [
        ExtractableAttribute(name="start_date", kind="DateTime", description=None),
        ExtractableAttribute(name="end_date", kind="DateTime", description=None),
    ]
    response = json.dumps({"start_date": "2026-01-01", "end_date": None})
    result = parse_extraction_response(response_text=response, attributes=attributes)
    assert "end_date" not in result
    assert result["start_date"] == "2026-01-01"


def test_parse_extraction_response_ignores_unknown_keys() -> None:
    attributes = [
        ExtractableAttribute(name="start_date", kind="DateTime", description=None),
    ]
    response = json.dumps({"start_date": "2026-01-01", "unknown_key": "should be ignored"})
    result = parse_extraction_response(response_text=response, attributes=attributes)
    assert "unknown_key" not in result
    assert "start_date" in result


def test_parse_extraction_response_handles_json_in_text() -> None:
    attributes = [ExtractableAttribute(name="title", kind="Text", description=None)]
    response = 'Here is the extracted data:\n{"title": "My Contract"}\n'
    result = parse_extraction_response(response_text=response, attributes=attributes)
    assert result == {"title": "My Contract"}


def test_parse_extraction_response_returns_empty_on_garbage() -> None:
    attributes = [ExtractableAttribute(name="title", kind="Text", description=None)]
    result = parse_extraction_response(response_text="not json at all", attributes=attributes)
    assert result == {}


@pytest.mark.parametrize(
    "response",
    [
        "null",
        "42",
        '"just a string"',
        "[]",
    ],
)
def test_parse_extraction_response_returns_empty_on_non_dict_json(response: str) -> None:
    attributes = [ExtractableAttribute(name="title", kind="Text", description=None)]
    result = parse_extraction_response(response_text=response, attributes=attributes)
    assert result == {}


# ---------------------------------------------------------------------------
# get_extractable_relationships
# ---------------------------------------------------------------------------


def test_get_extractable_relationships_returns_attribute_kind_one() -> None:
    schema = _FakeNodeSchema(
        attributes=[],
        relationships=[
            _FakeRelationshipSchema(name="provider", peer="InfraProvider", kind="Attribute", cardinality="one"),
            _FakeRelationshipSchema(name="site", peer="LocationSite", kind="Attribute", cardinality="one"),
        ],
    )
    result = get_extractable_relationships(schema)  # type: ignore[arg-type]
    names = [r.name for r in result]
    assert "provider" in names
    assert "site" in names


def test_get_extractable_relationships_excludes_generic_kind() -> None:
    schema = _FakeNodeSchema(
        attributes=[],
        relationships=[
            _FakeRelationshipSchema(name="tags", peer="BuiltinTag", kind="Generic", cardinality="many"),
            _FakeRelationshipSchema(name="provider", peer="InfraProvider", kind="Attribute", cardinality="one"),
        ],
    )
    result = get_extractable_relationships(schema)  # type: ignore[arg-type]
    names = [r.name for r in result]
    assert "provider" in names
    assert "tags" not in names


def test_get_extractable_relationships_excludes_cardinality_many() -> None:
    schema = _FakeNodeSchema(
        attributes=[],
        relationships=[
            _FakeRelationshipSchema(name="interfaces", peer="InfraInterface", kind="Attribute", cardinality="many"),
            _FakeRelationshipSchema(name="site", peer="LocationSite", kind="Attribute", cardinality="one"),
        ],
    )
    result = get_extractable_relationships(schema)  # type: ignore[arg-type]
    names = [r.name for r in result]
    assert "site" in names
    assert "interfaces" not in names


def test_get_extractable_relationships_excludes_read_only() -> None:
    schema = _FakeNodeSchema(
        attributes=[],
        relationships=[
            _FakeRelationshipSchema(name="editable_rel", peer="InfraProvider", kind="Attribute", cardinality="one", read_only=False),
            _FakeRelationshipSchema(name="readonly_rel", peer="InfraProvider", kind="Attribute", cardinality="one", read_only=True),
        ],
    )
    result = get_extractable_relationships(schema)  # type: ignore[arg-type]
    names = [r.name for r in result]
    assert "editable_rel" in names
    assert "readonly_rel" not in names


# ---------------------------------------------------------------------------
# build_extraction_prompt with relationships
# ---------------------------------------------------------------------------


def test_build_extraction_prompt_includes_relationships_without_choices() -> None:
    attributes = [ExtractableAttribute(name="start_date", kind="DateTime", description="Contract start date")]
    relationships = [
        ExtractableRelationship(name="provider", peer="InfraProvider", description="The service provider"),
        ExtractableRelationship(name="site", peer="LocationSite", description=None),
    ]
    prompt = build_extraction_prompt(
        attributes=attributes,
        file_name="contract.pdf",
        file_type="application/pdf",
        relationships=relationships,
    )
    assert "provider" in prompt
    assert "InfraProvider" in prompt
    assert "The service provider" in prompt
    assert "site" in prompt
    assert "LocationSite" in prompt
    assert "Related object fields" in prompt


def test_build_extraction_prompt_relationship_with_peer_choices() -> None:
    relationships = [
        ExtractableRelationship(
            name="site",
            peer="LocationSite",
            description=None,
            peer_choices=["AMS-01", "BRU-01", "PAR-02"],
        )
    ]
    prompt = build_extraction_prompt(
        attributes=[],
        file_name="contract.pdf",
        file_type="application/pdf",
        relationships=relationships,
    )
    assert "AMS-01" in prompt
    assert "BRU-01" in prompt
    assert "PAR-02" in prompt
    assert "one of:" in prompt
    # When choices are provided, the raw peer type name is not shown
    assert "LocationSite" not in prompt


def test_build_extraction_prompt_no_relationships_section_when_empty() -> None:
    attributes = [ExtractableAttribute(name="start_date", kind="DateTime", description=None)]
    prompt = build_extraction_prompt(
        attributes=attributes, file_name="f.pdf", file_type="application/pdf", relationships=[]
    )
    assert "Related object fields" not in prompt


# ---------------------------------------------------------------------------
# parse_extraction_response with relationships
# ---------------------------------------------------------------------------


def test_parse_extraction_response_includes_relationship_values() -> None:
    attributes = [ExtractableAttribute(name="start_date", kind="DateTime", description=None)]
    relationships = [ExtractableRelationship(name="provider", peer="InfraProvider", description=None)]
    response = json.dumps({"start_date": "2026-01-01", "provider": "Acme Telecom"})
    result = parse_extraction_response(response_text=response, attributes=attributes, relationships=relationships)
    assert result == {"start_date": "2026-01-01", "provider": "Acme Telecom"}


def test_parse_extraction_response_drops_null_relationship() -> None:
    attributes = [ExtractableAttribute(name="start_date", kind="DateTime", description=None)]
    relationships = [ExtractableRelationship(name="provider", peer="InfraProvider", description=None)]
    response = json.dumps({"start_date": "2026-01-01", "provider": None})
    result = parse_extraction_response(response_text=response, attributes=attributes, relationships=relationships)
    assert "provider" not in result


def test_parse_extraction_response_ignores_unknown_relationship_key() -> None:
    attributes: list[ExtractableAttribute] = []
    relationships = [ExtractableRelationship(name="provider", peer="InfraProvider", description=None)]
    response = json.dumps({"provider": "Acme", "other_rel": "should be ignored"})
    result = parse_extraction_response(response_text=response, attributes=attributes, relationships=relationships)
    assert result == {"provider": "Acme"}
    assert "other_rel" not in result
