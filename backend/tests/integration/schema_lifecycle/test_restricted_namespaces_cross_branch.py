"""Integration test for restricted_namespaces validation across branches.

Verifies that the schema integrity check catches namespace restriction violations
when schema changes are split across branches:
- Main branch: adds restricted_namespaces to a generic
- Feature branch: adds a node inheriting from the generic with a non-compliant namespace

The candidate schema (merge of both) must fail validation during process().
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.schema import SchemaRoot

from ..shared import load_schema
from .shared import TestSchemaLifecycleBase

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


class TestRestrictedNamespacesCrossBranch(TestSchemaLifecycleBase):
    """Test that merging schemas from two branches detects restricted_namespaces violations.

    Scenario:
    1. Load initial schema: generic BaseProblem (no restriction) + SupportProblem + SupportIncident
    2. On main: add restricted_namespaces: ["Support"] to BaseProblem
    3. On branch: add BaselineProblem (namespace: Baseline, inherits BaseProblem)
    4. Build candidate schema (main + branch) and process() -> should raise ValueError
    """

    @pytest.fixture(scope="class")
    def schema_problem_generic(self) -> dict[str, Any]:
        return {
            "name": "Problem",
            "namespace": "Base",
            "description": "Generic Problem",
            "label": "Base Problem",
            "include_in_menu": False,
            "order_by": ["name__value"],
            "display_labels": ["name__value"],
            "attributes": [
                {"name": "name", "kind": "Text", "order_weight": 1000},
                {"name": "description", "kind": "Text", "optional": True, "order_weight": 1200},
            ],
        }

    @pytest.fixture(scope="class")
    def schema_problem_generic_with_restriction(self) -> dict[str, Any]:
        return {
            "name": "Problem",
            "namespace": "Base",
            "description": "Generic Problem",
            "label": "Base Problem",
            "include_in_menu": False,
            "order_by": ["name__value"],
            "display_labels": ["name__value"],
            "restricted_namespaces": ["Support"],
            "attributes": [
                {"name": "name", "kind": "Text", "order_weight": 1000},
                {"name": "description", "kind": "Text", "optional": True, "order_weight": 1200},
            ],
        }

    @pytest.fixture(scope="class")
    def schema_support_problem_node(self) -> dict[str, Any]:
        return {
            "name": "Problem",
            "namespace": "Support",
            "label": "Problem",
            "display_labels": ["name__value"],
            "human_friendly_id": ["name__value"],
            "generate_profile": True,
            "include_in_menu": True,
            "inherit_from": ["BaseProblem"],
            "attributes": [
                {"name": "name", "kind": "Text", "order_weight": 1000},
            ],
        }

    @pytest.fixture(scope="class")
    def schema_support_incident_node(self) -> dict[str, Any]:
        return {
            "name": "Incident",
            "namespace": "Support",
            "label": "Incident",
            "display_labels": ["name__value"],
            "human_friendly_id": ["name__value"],
            "generate_profile": True,
            "include_in_menu": True,
            "inherit_from": ["BaseProblem"],
            "attributes": [
                {"name": "name", "kind": "Text", "order_weight": 1000},
            ],
        }

    @pytest.fixture(scope="class")
    def schema_baseline_problem_node(self) -> dict[str, Any]:
        """Node with namespace Baseline that violates the Support restriction."""
        return {
            "name": "Problem",
            "namespace": "Baseline",
            "label": "Baseline Problem",
            "display_labels": ["name__value"],
            "human_friendly_id": ["name__value"],
            "generate_profile": True,
            "include_in_menu": True,
            "inherit_from": ["BaseProblem"],
            "attributes": [
                {"name": "name", "kind": "Text", "order_weight": 1000},
            ],
        }

    @pytest.fixture(scope="class")
    def schema_initial(
        self,
        schema_problem_generic: dict[str, Any],
        schema_support_problem_node: dict[str, Any],
        schema_support_incident_node: dict[str, Any],
    ) -> dict[str, Any]:
        """Initial schema: generic without restriction + two compliant nodes."""
        return {
            "version": "1.0",
            "generics": [schema_problem_generic],
            "nodes": [schema_support_problem_node, schema_support_incident_node],
        }

    @pytest.fixture(scope="class")
    def schema_main_with_restriction(
        self,
        schema_problem_generic_with_restriction: dict[str, Any],
        schema_support_problem_node: dict[str, Any],
        schema_support_incident_node: dict[str, Any],
    ) -> dict[str, Any]:
        """Main branch schema: generic now has restricted_namespaces: [Support]."""
        return {
            "version": "1.0",
            "generics": [schema_problem_generic_with_restriction],
            "nodes": [schema_support_problem_node, schema_support_incident_node],
        }

    @pytest.fixture(scope="class")
    def schema_branch_with_baseline(
        self,
        schema_problem_generic: dict[str, Any],
        schema_support_problem_node: dict[str, Any],
        schema_support_incident_node: dict[str, Any],
        schema_baseline_problem_node: dict[str, Any],
    ) -> dict[str, Any]:
        """Branch schema: adds BaselineProblem node (non-compliant namespace)."""
        return {
            "version": "1.0",
            "generics": [schema_problem_generic],
            "nodes": [
                schema_support_problem_node,
                schema_support_incident_node,
                schema_baseline_problem_node,
            ],
        }

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        schema_initial: dict[str, Any],
    ) -> None:
        await load_schema(db=db, schema=schema_initial)

    async def test_cross_branch_merge_detects_namespace_violation(
        self,
        initial_dataset: None,
        schema_main_with_restriction: dict[str, Any],
        schema_branch_with_baseline: dict[str, Any],
    ) -> None:
        """Simulate the proposed change schema integrity check.

        Build a candidate schema the same way run_proposed_change_schema_integrity_check does:
        - dest_schema = main branch schema (with restricted_namespaces on the generic)
        - source_schema = feature branch schema (with the violating BaselineProblem node)
        - candidate = dest_schema.update(source_schema)
        - candidate.process() should raise ValueError about namespace restriction
        """
        # Simulate main branch: load schema with restriction
        main_schema: SchemaBranch = registry.schema.get_schema_branch(name=registry.default_branch).duplicate()
        main_schema.load_schema(schema=SchemaRoot(**schema_main_with_restriction))

        # Simulate feature branch: load schema with non-compliant node
        branch_schema: SchemaBranch = registry.schema.get_schema_branch(name=registry.default_branch).duplicate()
        branch_schema.load_schema(schema=SchemaRoot(**schema_branch_with_baseline))

        # Build candidate schema the way the proposed change integrity check does:
        # candidate_schema = dest_schema.duplicate(); candidate_schema.update(schema=source_schema)
        candidate_schema = main_schema.duplicate()
        candidate_schema.update(schema=branch_schema)

        # This must detect the violation: BaselineProblem (namespace: Baseline)
        # inherits from BaseProblem which has restricted_namespaces: ["Support"]
        with pytest.raises(ValueError, match=r"restricted namespaces.*Baseline"):
            candidate_schema.duplicate().process()
