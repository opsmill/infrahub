from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.api.schema import SchemaLoadAPI
from infrahub.core.constants import UpdateValidationErrorType
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.attribute_parameters import (
    NumberPoolParameters,
    NumberPoolRangeParameters,
    TextAttributeParameters,
)
from infrahub.core.schema.schema_branch import SchemaBranch

WIDGET_GADGET_SCHEMA: dict[str, Any] = {
    "version": "1.0",
    "nodes": [
        {
            "name": "Widget",
            "namespace": "Test",
            "attributes": [{"name": "name", "kind": "Text", "unique": True}],
            "relationships": [
                {
                    "name": "gadgets",
                    "peer": "TestGadget",
                    "cardinality": "many",
                    "identifier": "widget__gadget",
                    "optional": True,
                }
            ],
        },
        {
            "name": "Gadget",
            "namespace": "Test",
            "attributes": [{"name": "name", "kind": "Text", "unique": True}],
        },
    ],
}


def _build_schema() -> SchemaBranch:
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**WIDGET_GADGET_SCHEMA))
    schema.process()
    return schema


async def test_relationship_identifier_update_is_not_supported() -> None:
    """Changing a relationship's identifier must be rejected rather than silently orphaning data."""
    schema = _build_schema()

    candidate = schema.duplicate()
    widget = candidate.get_node(name="TestWidget", duplicate=True)
    relationship = widget.get_relationship(name="gadgets")
    relationship.identifier = "widget__gadget_renamed"
    candidate.set(name="TestWidget", schema=widget)

    diff = schema.diff(other=candidate)
    result = schema.validate_update(other=candidate, diff=diff)

    assert len(result.errors) == 1
    error = result.errors[0]
    assert error.error == UpdateValidationErrorType.NOT_SUPPORTED
    assert error.path.schema_kind == "TestWidget"
    assert error.path.field_name == "gadgets"
    assert error.path.property_name == "identifier"
    assert result.migrations == []


async def test_schema_diff_constraint_scoped_to_changed_attribute() -> None:
    """A change to one attribute property emits only that attribute's constraint, not the kind's uniqueness constraint."""
    schema = _build_schema()

    candidate = schema.duplicate()
    widget = candidate.get_node(name="TestWidget", duplicate=True)
    parameters = widget.get_attribute(name="name").parameters
    assert isinstance(parameters, TextAttributeParameters)
    parameters.max_length = 20
    candidate.set(name="TestWidget", schema=widget)

    diff = schema.diff(other=candidate)
    result = schema.validate_update(other=candidate, diff=diff)

    constraint_names = {c.constraint_name for c in result.constraints}
    assert constraint_names
    assert "node.uniqueness_constraints.update" not in constraint_names
    # every emitted constraint is scoped to the single changed element
    assert all(c.path.schema_kind == "TestWidget" and c.path.field_name == "name" for c in result.constraints)


async def test_number_pool_ranges_change_emits_a_supported_constraint() -> None:
    """A change limited to the declared ranges of a NumberPool attribute is validated rather than refused."""
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(
        schema=SchemaRoot(
            version="1.0",
            nodes=[
                {
                    "name": "Widget",
                    "namespace": "Test",
                    "attributes": [
                        {"name": "name", "kind": "Text", "unique": True},
                        {
                            "name": "number",
                            "kind": "NumberPool",
                            "read_only": True,
                            "parameters": {"ranges": [{"start": 1, "end": 100}]},
                        },
                    ],
                }
            ],
        )
    )
    schema.process()

    candidate = schema.duplicate()
    widget = candidate.get_node(name="TestWidget", duplicate=True)
    parameters = widget.get_attribute(name="number").parameters
    assert isinstance(parameters, NumberPoolParameters)
    parameters.ranges = [NumberPoolRangeParameters(start=1, end=50), NumberPoolRangeParameters(start=80, end=100)]
    candidate.set(name="TestWidget", schema=widget)

    diff = schema.diff(other=candidate)
    result = schema.validate_update(other=candidate, diff=diff)

    assert result.errors == []
    assert [c.constraint_name for c in result.constraints] == ["attribute.parameters.ranges.update"]
    assert result.constraints[0].path.property_name == "parameters.ranges"


@dataclass(frozen=True)
class ReorderedScopeCase:
    name: str
    declared: list[str]
    reordered: list[str]


REORDERED_SCOPE_CASES = [
    ReorderedScopeCase(name="to-sorted-order", declared=["site", "role"], reordered=["role", "site"]),
    ReorderedScopeCase(name="from-sorted-order", declared=["role", "site"], reordered=["site", "role"]),
]


@pytest.mark.parametrize("case", REORDERED_SCOPE_CASES, ids=[case.name for case in REORDERED_SCOPE_CASES])
async def test_number_pool_allocation_scope_reordered_is_not_a_change(case: ReorderedScopeCase) -> None:
    """Reordering a declared allocation scope keeps the same divisions, so it is not a change."""
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(
        schema=SchemaRoot(
            version="1.0",
            nodes=[
                {
                    "name": "Widget",
                    "namespace": "Test",
                    "attributes": [
                        {"name": "role", "kind": "Text"},
                        {"name": "site", "kind": "Text"},
                        {
                            "name": "number",
                            "kind": "NumberPool",
                            "read_only": True,
                            "parameters": {
                                "ranges": [{"start": 1, "end": 100}],
                                "allocation_scope": case.declared,
                                "number_pool_id": "widget-number-pool",
                            },
                        },
                    ],
                }
            ],
        )
    )
    schema.process(validate_schema=False)

    candidate = schema.duplicate()
    widget = candidate.get_node(name="TestWidget", duplicate=True)
    parameters = widget.get_attribute(name="number").parameters
    assert isinstance(parameters, NumberPoolParameters)
    parameters.allocation_scope = case.reordered
    candidate.set(name="TestWidget", schema=widget)

    diff = schema.diff(other=candidate)
    result = schema.validate_update(other=candidate, diff=diff)

    assert diff.all == []
    assert result.errors == []
    assert result.constraints == []


def _widget_with_number_pool(number_attribute: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": "1.0",
        "nodes": [
            {
                "name": "Widget",
                "namespace": "Test",
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "number", "kind": "NumberPool", "read_only": True, **number_attribute},
                ],
            }
        ],
    }


@dataclass(frozen=True)
class ReloadedPoolDeclarationCase:
    name: str
    stored_parameters: dict[str, Any]
    reloaded_attribute: dict[str, Any]
    """The NumberPool attribute fields of the reloaded schema, besides its name and kind."""
    expected_declaration: tuple[int | None, int | None, list[tuple[int, int]]]
    """The stored declaration after the reload, as (start_range, end_range, ranges)."""
    expected_changed_parameters: list[str]
    """The NumberPool parameters the reload changes, each one checked against the stored data before the load."""


RELOADED_POOL_DECLARATION_CASES = [
    ReloadedPoolDeclarationCase(
        name="empty-parameters-keep-the-ranges",
        stored_parameters={"ranges": [{"start": 1, "end": 100}, {"start": 200, "end": 300}]},
        reloaded_attribute={"parameters": {}},
        expected_declaration=(None, None, [(1, 100), (200, 300)]),
        expected_changed_parameters=[],
    ),
    ReloadedPoolDeclarationCase(
        name="parameters-without-a-range-key-keep-the-ranges",
        stored_parameters={"ranges": [{"start": 1, "end": 100}, {"start": 200, "end": 300}]},
        reloaded_attribute={"parameters": {"allocation_scope": ["name"]}},
        expected_declaration=(None, None, [(1, 100), (200, 300)]),
        expected_changed_parameters=["allocation_scope"],
    ),
    ReloadedPoolDeclarationCase(
        name="empty-range-list-removes-the-ranges",
        stored_parameters={"ranges": [{"start": 1, "end": 100}, {"start": 200, "end": 300}]},
        reloaded_attribute={"parameters": {"ranges": []}},
        expected_declaration=(None, None, []),
        expected_changed_parameters=["ranges"],
    ),
    ReloadedPoolDeclarationCase(
        name="empty-parameters-keep-the-shorthand",
        stored_parameters={"start_range": 50, "end_range": 1200},
        reloaded_attribute={"parameters": {}},
        expected_declaration=(50, 1200, []),
        expected_changed_parameters=[],
    ),
    ReloadedPoolDeclarationCase(
        name="parameters-without-a-range-key-keep-the-shorthand",
        stored_parameters={"start_range": 50, "end_range": 1200},
        reloaded_attribute={"parameters": {"allocation_scope": ["name"]}},
        expected_declaration=(50, 1200, []),
        expected_changed_parameters=["allocation_scope"],
    ),
    ReloadedPoolDeclarationCase(
        name="empty-range-list-removes-the-shorthand",
        stored_parameters={"start_range": 50, "end_range": 1200},
        reloaded_attribute={"parameters": {"ranges": []}},
        expected_declaration=(None, None, []),
        expected_changed_parameters=["end_range", "start_range"],
    ),
    ReloadedPoolDeclarationCase(
        name="omitted-parameters-keep-the-ranges",
        stored_parameters={"ranges": [{"start": 1, "end": 100}, {"start": 200, "end": 300}]},
        reloaded_attribute={},
        expected_declaration=(None, None, [(1, 100), (200, 300)]),
        expected_changed_parameters=[],
    ),
    ReloadedPoolDeclarationCase(
        name="omitted-parameters-keep-the-shorthand",
        stored_parameters={"start_range": 50, "end_range": 1200},
        reloaded_attribute={},
        expected_declaration=(50, 1200, []),
        expected_changed_parameters=[],
    ),
]


@dataclass(frozen=True)
class ReloadOutcome:
    declaration: tuple[int | None, int | None, list[tuple[int, int]]]
    """The stored declaration after the reload, as (start_range, end_range, ranges)."""
    changed_parameters: list[str]
    """The NumberPool parameters the update validation checks against the stored data, sorted."""


def _reload_number_pool_declaration(
    case: ReloadedPoolDeclarationCase, other_files: list[dict[str, Any]]
) -> ReloadOutcome:
    schema = SchemaBranch(cache={}, name="test")
    schema.load_schema(schema=SchemaRoot(**_widget_with_number_pool({"parameters": case.stored_parameters})))
    schema.process()

    candidate = schema.duplicate()
    reloaded = SchemaLoadAPI.model_validate(_widget_with_number_pool(case.reloaded_attribute)).internal_schema
    for other_file in other_files:
        reloaded = reloaded.merge(schema=SchemaLoadAPI.model_validate(other_file).internal_schema)
    candidate.load_schema(schema=reloaded)
    candidate.process()

    result = schema.validate_update(other=candidate, diff=schema.diff(other=candidate))
    assert result.errors == []

    parameters = candidate.get_node(name="TestWidget", duplicate=False).get_attribute(name="number").parameters
    assert isinstance(parameters, NumberPoolParameters)
    return ReloadOutcome(
        declaration=(
            parameters.start_range,
            parameters.end_range,
            [(pool_range.start, pool_range.end) for pool_range in parameters.ranges],
        ),
        changed_parameters=sorted(
            constraint.constraint_name.removeprefix("attribute.parameters.").removesuffix(".update")
            for constraint in result.constraints
        ),
    )


@pytest.mark.parametrize("case", [pytest.param(tc, id=tc.name) for tc in RELOADED_POOL_DECLARATION_CASES])
async def test_reloaded_number_pool_declaration(case: ReloadedPoolDeclarationCase) -> None:
    """Only an explicitly empty range list removes the stored ranges, a reload that leaves the ranges out keeps them."""
    outcome = _reload_number_pool_declaration(case=case, other_files=[])

    assert outcome.declaration == case.expected_declaration
    assert outcome.changed_parameters == case.expected_changed_parameters


UNRELATED_SCHEMA_FILE: dict[str, Any] = {
    "version": "1.0",
    "nodes": [{"name": "Gadget", "namespace": "Test", "attributes": [{"name": "name", "kind": "Text"}]}],
}

MERGED_LOAD_CASES = [
    ReloadedPoolDeclarationCase(
        name="empty-range-list-still-removes-the-ranges",
        stored_parameters={"ranges": [{"start": 1, "end": 100}, {"start": 200, "end": 300}]},
        reloaded_attribute={"parameters": {"ranges": []}},
        expected_declaration=(None, None, []),
        expected_changed_parameters=["ranges"],
    ),
    ReloadedPoolDeclarationCase(
        name="empty-parameters-still-keep-the-ranges",
        stored_parameters={"ranges": [{"start": 1, "end": 100}, {"start": 200, "end": 300}]},
        reloaded_attribute={"parameters": {}},
        expected_declaration=(None, None, [(1, 100), (200, 300)]),
        expected_changed_parameters=[],
    ),
]


@pytest.mark.parametrize("case", [pytest.param(tc, id=tc.name) for tc in MERGED_LOAD_CASES])
async def test_reloaded_number_pool_declaration_in_a_load_of_several_files(case: ReloadedPoolDeclarationCase) -> None:
    """A load of several files merges them through a dump and a parse, which must keep the declared ranges as sent."""
    outcome = _reload_number_pool_declaration(case=case, other_files=[UNRELATED_SCHEMA_FILE])

    assert outcome.declaration == case.expected_declaration
    assert outcome.changed_parameters == case.expected_changed_parameters
