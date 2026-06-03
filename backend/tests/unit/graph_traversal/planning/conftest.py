"""Pytest fixtures for graph-traversal planner unit tests.

Uses real ``SchemaBranch`` / ``Branch`` / ``PermissionResolver`` constructed via
``backend/tests/helpers/graph_traversal/builders.py``. No database is required —
``SchemaBranch.process(validate_schema=False)`` populates relationship
identifiers and ``GenericSchema.used_by`` from a plain ``SchemaRoot``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import RelationshipCardinality, RelationshipDirection, RelationshipKind
from infrahub.core.schema import NodeSchema, RelationshipSchema
from tests.helpers.graph_traversal.builders import build_schema_branch

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch import SchemaBranch


def _node(
    name: str, *, namespace: str = "Testing", relationships: list[RelationshipSchema] | None = None
) -> NodeSchema:
    return NodeSchema(name=name, namespace=namespace, relationships=relationships or [])


def _rel(
    *,
    name: str,
    peer: str,
    identifier: str,
    direction: RelationshipDirection = RelationshipDirection.BIDIR,
) -> RelationshipSchema:
    return RelationshipSchema(
        name=name,
        kind=RelationshipKind.GENERIC,
        peer=peer,
        cardinality=RelationshipCardinality.ONE,
        identifier=identifier,
        direction=direction,
    )


@pytest.fixture
def linear_a_b_c_schema() -> SchemaBranch:
    """A→B→C linear schema with explicit BIDIR relationship identifiers."""
    return build_schema_branch(
        nodes=[
            _node("KindA", relationships=[_rel(name="rel_b", peer="TestingKindB", identifier="a__b")]),
            _node("KindB", relationships=[_rel(name="rel_c", peer="TestingKindC", identifier="b__c")]),
            _node("KindC"),
        ],
    )


@pytest.fixture
def disconnected_schema() -> SchemaBranch:
    """Two kinds with no schema relationship between them."""
    return build_schema_branch(nodes=[_node("Alpha"), _node("Beta")])
