from __future__ import annotations

import copy
import re
from dataclasses import dataclass

import pytest

from infrahub.core.registry import registry
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.exceptions import InitializationError, ValidationError
from tests.helpers.number_pool import (
    SCOPED_DEVICE,
    SCOPED_HOLDER,
    SCOPED_LINK,
    SCOPED_POD_HOLDER,
    SCOPED_RACK,
    SCOPED_SITE,
)


def _with_pooled_vlan_id[SchemaT: (NodeSchema, GenericSchema)](schema: SchemaT, scope: list[str] | None) -> SchemaT:
    pooled: SchemaT = copy.deepcopy(schema)
    pooled.attributes = [attribute for attribute in pooled.attributes if attribute.name != "vlan_id"]
    pooled.attributes.append(
        AttributeSchema(
            name="vlan_id",
            kind="NumberPool",
            optional=False,
            read_only=True,
            parameters=NumberPoolParameters(start_range=1, end_range=100, allocation_scope=scope),
        )
    )
    return pooled


def _schema(device: NodeSchema = SCOPED_DEVICE, holder: GenericSchema = SCOPED_HOLDER) -> SchemaRoot:
    return SchemaRoot(generics=[holder], nodes=[SCOPED_SITE, SCOPED_RACK, SCOPED_LINK, device, SCOPED_POD_HOLDER])


def _device_schema(scope: list[str] | None) -> SchemaRoot:
    return _schema(device=_with_pooled_vlan_id(SCOPED_DEVICE, scope=scope))


def _unvalidated_schema_branch(name: str, schema: SchemaRoot) -> SchemaBranch:
    """Return the schema as a load holds it before validation: processed, with no field saved and so no field id."""
    schema_branch = SchemaBranch(cache={}, name=name)
    schema_branch.load_schema(schema=copy.deepcopy(schema))
    schema_branch.process(validate_schema=False)
    return schema_branch


@dataclass(frozen=True)
class RefusedDeclarationCase:
    name: str
    schema: SchemaRoot
    message: str


REFUSED_DECLARATION_CASES = [
    RefusedDeclarationCase(
        name="optional-relationship",
        schema=_device_schema(scope=["site", "rack"]),
        message='ScopeDevice.vlan_id: allocation_scope: "rack" is optional; a scope element must be required on'
        " ScopeDevice",
    ),
    RefusedDeclarationCase(
        name="relationship-of-cardinality-many",
        schema=_device_schema(scope=["links"]),
        message='ScopeDevice.vlan_id: allocation_scope: "links" has cardinality many; a scope element must be a'
        " relationship of cardinality one",
    ),
    RefusedDeclarationCase(
        name="path",
        schema=_device_schema(scope=["site__name"]),
        message='ScopeDevice.vlan_id: allocation_scope: "site__name" is a path; a scope element must be an attribute'
        " or a relationship of ScopeDevice itself",
    ),
    RefusedDeclarationCase(
        name="absent-element",
        schema=_device_schema(scope=["region"]),
        message='ScopeDevice.vlan_id: allocation_scope: "region" is not an attribute or a relationship of ScopeDevice'
        " on branch main",
    ),
    RefusedDeclarationCase(
        name="list-attribute",
        schema=_device_schema(scope=["tags"]),
        message='ScopeDevice.vlan_id: allocation_scope: "tags" is of kind List; a scope element must hold a single'
        " scalar value",
    ),
    RefusedDeclarationCase(
        name="element-declared-twice",
        schema=_device_schema(scope=["site", "site"]),
        message='ScopeDevice.vlan_id: allocation_scope: "site" appears more than once',
    ),
    RefusedDeclarationCase(
        name="tracked-attribute",
        schema=_device_schema(scope=["vlan_id"]),
        message='ScopeDevice.vlan_id: allocation_scope: "vlan_id" is the attribute the pool allocates; it cannot'
        " divide the pool",
    ),
    RefusedDeclarationCase(
        name="element-of-the-implementing-kind-only",
        schema=_schema(holder=_with_pooled_vlan_id(SCOPED_HOLDER, scope=["pod"])),
        message='ScopeHolder.vlan_id: allocation_scope: "pod" is not declared on the generic ScopeHolder',
    ),
]


@dataclass(frozen=True)
class AcceptedDeclarationCase:
    name: str
    schema: SchemaRoot


ACCEPTED_DECLARATION_CASES = [
    AcceptedDeclarationCase(name="fields-the-load-adds", schema=_device_schema(scope=["site", "role"])),
    AcceptedDeclarationCase(name="no-scope", schema=_device_schema(scope=None)),
    AcceptedDeclarationCase(
        name="element-declared-on-the-generic",
        schema=_schema(holder=_with_pooled_vlan_id(SCOPED_HOLDER, scope=["site"])),
    ),
]


@pytest.mark.parametrize("case", REFUSED_DECLARATION_CASES, ids=lambda case: case.name)
def test_declared_scope_is_refused(case: RefusedDeclarationCase) -> None:
    schema_branch = _unvalidated_schema_branch(name="main", schema=case.schema)

    with pytest.raises(ValidationError, match=f"^{re.escape(case.message)}$"):
        schema_branch.validate_attribute_parameters()


@pytest.mark.parametrize("case", ACCEPTED_DECLARATION_CASES, ids=lambda case: case.name)
def test_declared_scope_is_accepted(case: AcceptedDeclarationCase) -> None:
    schema_branch = _unvalidated_schema_branch(name="main", schema=case.schema)

    schema_branch.validate_attribute_parameters()


def _register_default_branch_schema(monkeypatch: pytest.MonkeyPatch, schema: SchemaRoot | None) -> None:
    schema_manager = SchemaManager()
    if schema is not None:
        schema_manager.set_schema_branch(
            name=registry.default_branch, schema=_unvalidated_schema_branch(name="main", schema=schema)
        )
    monkeypatch.setattr(registry, "_schema", schema_manager)


class TestDeclaredScopeOnABranch:
    """On a branch, the declared names resolve against the schema of the default branch."""

    @pytest.fixture
    def default_branch_schema(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _register_default_branch_schema(monkeypatch=monkeypatch, schema=_schema())

    @pytest.mark.usefixtures("default_branch_schema")
    def test_element_only_on_the_branch_is_refused(self) -> None:
        device = _with_pooled_vlan_id(SCOPED_DEVICE, scope=["zone"])
        device.attributes.append(AttributeSchema(name="zone", kind="Text", optional=False))
        schema_branch = _unvalidated_schema_branch(name="branch1", schema=_schema(device=device))

        with pytest.raises(
            ValidationError,
            match="^"
            + re.escape(
                'ScopeDevice.vlan_id: allocation_scope: "zone" is not an attribute or a relationship of ScopeDevice'
                " on branch main"
            )
            + "$",
        ):
            schema_branch.validate_attribute_parameters()

    @pytest.mark.usefixtures("default_branch_schema")
    def test_element_of_the_default_branch_is_accepted(self) -> None:
        schema_branch = _unvalidated_schema_branch(name="branch1", schema=_device_schema(scope=["site"]))

        schema_branch.validate_attribute_parameters()

    @pytest.mark.usefixtures("default_branch_schema")
    def test_element_made_optional_by_the_same_load_is_refused(self) -> None:
        device = _with_pooled_vlan_id(SCOPED_DEVICE, scope=["site"])
        device.get_relationship(name="site").optional = True
        schema_branch = _unvalidated_schema_branch(name="branch1", schema=_schema(device=device))

        with pytest.raises(
            ValidationError,
            match="^"
            + re.escape(
                'ScopeDevice.vlan_id: allocation_scope: "site" is optional; a scope element must be required on'
                " ScopeDevice"
            )
            + "$",
        ):
            schema_branch.validate_attribute_parameters()

    def test_new_declaration_without_the_schema_of_the_default_branch_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _register_default_branch_schema(monkeypatch=monkeypatch, schema=None)
        schema_branch = _unvalidated_schema_branch(name="branch1", schema=_device_schema(scope=["site"]))

        with pytest.raises(
            InitializationError,
            match="^"
            + re.escape(
                "The schema of the default branch main is not loaded; an allocation scope declared on branch branch1"
                " cannot be resolved"
            )
            + "$",
        ):
            schema_branch.validate_attribute_parameters()
