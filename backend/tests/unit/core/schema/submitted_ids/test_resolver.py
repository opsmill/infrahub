from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import HashableModelState
from infrahub.core.schema import (
    AttributeSchema,
    GenericSchema,
    NodeExtensionSchema,
    NodeSchema,
    RelationshipSchema,
    SchemaExtension,
    SchemaRoot,
    SchemaWarning,
    SchemaWarningKind,
    SchemaWarningType,
)
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.schema.submitted_ids.resolver import (
    IGNORED_ID_WARNING,
    SKIPPED_ABSENT_WARNING,
    SubmittedSchemaIdResolver,
)

if TYPE_CHECKING:
    from collections.abc import Collection, Sequence


class InMemorySchemaElementIdLookup:
    def __init__(self, existing_ids: set[str]) -> None:
        self.existing_ids = existing_ids
        self.calls: list[set[str]] = []

    async def get_existing_ids(self, ids: Collection[str]) -> set[str]:
        self.calls.append(set(ids))
        return self.existing_ids & set(ids)


@pytest.fixture(scope="module")
def stored_branch_schema() -> SchemaBranch:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(
        schema=SchemaRoot(
            generics=[
                GenericSchema(
                    id="g1",
                    name="Thing",
                    namespace="Testing",
                    attributes=[AttributeSchema(id="g1a", name="label", kind="Text")],
                )
            ],
            nodes=[
                NodeSchema(
                    id="n1",
                    name="Widget",
                    namespace="Testing",
                    inherit_from=["TestingThing"],
                    attributes=[AttributeSchema(id="n1a", name="serial", kind="Text")],
                    relationships=[
                        RelationshipSchema(id="n1r", name="parts", peer="TestingWidget", cardinality="many")
                    ],
                ),
                NodeSchema(
                    id="n2",
                    name="Gadget",
                    namespace="Testing",
                    attributes=[AttributeSchema(id="n2a", name="serial", kind="Text")],
                ),
            ],
        )
    )
    schema_branch.process()
    return schema_branch


def _attribute(
    name: str, element_id: str | None, state: HashableModelState = HashableModelState.PRESENT
) -> AttributeSchema:
    return AttributeSchema(id=element_id, name=name, kind="Text", state=state)


def _relationship(
    name: str, element_id: str | None, state: HashableModelState = HashableModelState.PRESENT
) -> RelationshipSchema:
    return RelationshipSchema(id=element_id, name=name, peer="TestingWidget", cardinality="many", state=state)


def _widget(
    element_id: str | None,
    attributes: list[AttributeSchema] | None = None,
    relationships: list[RelationshipSchema] | None = None,
    name: str = "Widget",
    state: HashableModelState = HashableModelState.PRESENT,
) -> NodeSchema:
    return NodeSchema(
        id=element_id,
        name=name,
        namespace="Testing",
        state=state,
        attributes=attributes or [],
        relationships=relationships or [],
    )


def _ignored_warning(*kinds: SchemaWarningKind) -> SchemaWarning:
    return SchemaWarning(type=SchemaWarningType.DEPRECATION, kinds=list(kinds), message=IGNORED_ID_WARNING)


def _skipped_warning(*kinds: SchemaWarningKind) -> SchemaWarning:
    return SchemaWarning(type=SchemaWarningType.DEPRECATION, kinds=list(kinds), message=SKIPPED_ABSENT_WARNING)


def _element_ids(schemas: Sequence[SchemaRoot]) -> dict[str, str | None]:
    element_ids: dict[str, str | None] = {}

    def add(label: str, element_id: str | None) -> None:
        # The same element written once with an ID and once without one has that ID.
        known_id = element_ids.get(label)
        assert known_id is None or element_id is None or known_id == element_id, f"{label} has two different IDs"
        if element_id is not None or label not in element_ids:
            element_ids[label] = element_id

    for schema in schemas:
        owners: list[GenericSchema | NodeSchema | NodeExtensionSchema] = [
            *schema.generics,
            *schema.nodes,
            *schema.extensions.nodes,
        ]
        for owner in owners:
            if not isinstance(owner, NodeExtensionSchema):
                add(owner.kind, owner.id)
            fields: list[AttributeSchema | RelationshipSchema] = [*owner.attributes, *owner.relationships]
            for field in fields:
                add(f"{owner.kind}.{field.name}", field.id)
    return element_ids


@dataclass
class ResolveCase:
    name: str
    submitted: list[SchemaRoot]
    existing_ids: set[str]
    expected_ids: dict[str, str | None]
    expected_absent_removed: list[str]
    expected_warnings: list[SchemaWarning]
    expected_errors: list[str]
    expected_lookup_calls: list[set[str]]


RESOLVE_CASES: list[ResolveCase] = [
    ResolveCase(
        name="same_branch_export",
        submitted=[
            SchemaRoot(
                generics=[
                    GenericSchema(id="g1", name="Thing", namespace="Testing", attributes=[_attribute("label", "g1a")])
                ],
                nodes=[
                    _widget(
                        "n1", attributes=[_attribute("serial", "n1a")], relationships=[_relationship("parts", "n1r")]
                    ),
                    NodeSchema(id="n2", name="Gadget", namespace="Testing", attributes=[_attribute("serial", "n2a")]),
                ],
            )
        ],
        existing_ids=set(),
        expected_ids={
            "TestingThing": "g1",
            "TestingThing.label": "g1a",
            "TestingWidget": "n1",
            "TestingWidget.serial": "n1a",
            "TestingWidget.parts": "n1r",
            "TestingGadget": "n2",
            "TestingGadget.serial": "n2a",
        },
        expected_absent_removed=[],
        expected_warnings=[],
        expected_errors=[],
        expected_lookup_calls=[],
    ),
    ResolveCase(
        name="attribute_unknown_id",
        submitted=[SchemaRoot(nodes=[_widget("n1", attributes=[_attribute("serial", "zzz")])])],
        existing_ids=set(),
        expected_ids={"TestingWidget": "n1", "TestingWidget.serial": None},
        expected_absent_removed=[],
        expected_warnings=[_ignored_warning(SchemaWarningKind(kind="TestingWidget", field="serial"))],
        expected_errors=[],
        expected_lookup_calls=[{"zzz"}],
    ),
    ResolveCase(
        name="relationship_unknown_id",
        submitted=[SchemaRoot(nodes=[_widget("n1", relationships=[_relationship("parts", "zzz")])])],
        existing_ids=set(),
        expected_ids={"TestingWidget": "n1", "TestingWidget.parts": None},
        expected_absent_removed=[],
        expected_warnings=[_ignored_warning(SchemaWarningKind(kind="TestingWidget", field="parts"))],
        expected_errors=[],
        expected_lookup_calls=[{"zzz"}],
    ),
    ResolveCase(
        name="node_unknown_id",
        submitted=[SchemaRoot(nodes=[_widget("zzz", attributes=[_attribute("serial", "n1a")])])],
        existing_ids=set(),
        expected_ids={"TestingWidget": None, "TestingWidget.serial": "n1a"},
        expected_absent_removed=[],
        expected_warnings=[_ignored_warning(SchemaWarningKind(kind="TestingWidget", field=None))],
        expected_errors=[],
        expected_lookup_calls=[{"zzz"}],
    ),
    ResolveCase(
        name="attribute_rename_by_stored_id",
        submitted=[SchemaRoot(nodes=[_widget("n1", attributes=[_attribute("model", "n1a")])])],
        existing_ids=set(),
        expected_ids={"TestingWidget": "n1", "TestingWidget.model": "n1a"},
        expected_absent_removed=[],
        expected_warnings=[],
        expected_errors=[],
        expected_lookup_calls=[],
    ),
    ResolveCase(
        name="node_rename_with_field_ids",
        submitted=[SchemaRoot(nodes=[_widget("n1", name="Renamed", attributes=[_attribute("serial", "n1a")])])],
        existing_ids=set(),
        expected_ids={"TestingRenamed": "n1", "TestingRenamed.serial": "n1a"},
        expected_absent_removed=[],
        expected_warnings=[],
        expected_errors=[],
        expected_lookup_calls=[],
    ),
    ResolveCase(
        name="attribute_id_deleted_or_other_branch",
        submitted=[SchemaRoot(nodes=[_widget("n1", attributes=[_attribute("serial", "old")])])],
        existing_ids={"old"},
        expected_ids={"TestingWidget": "n1", "TestingWidget.serial": "old"},
        expected_absent_removed=[],
        expected_warnings=[],
        expected_errors=["TestingWidget.serial: id 'old' belongs to a schema element that is not on this branch"],
        expected_lookup_calls=[{"old"}],
    ),
    ResolveCase(
        name="absent_attribute_id_in_database",
        submitted=[
            SchemaRoot(
                nodes=[
                    _widget(
                        "n1",
                        attributes=[_attribute("serial", "old", state=HashableModelState.ABSENT)],
                        relationships=[_relationship("parts", "n1r")],
                    )
                ]
            )
        ],
        existing_ids={"old"},
        expected_ids={"TestingWidget": "n1", "TestingWidget.parts": "n1r"},
        expected_absent_removed=["TestingWidget.serial"],
        expected_warnings=[_skipped_warning(SchemaWarningKind(kind="TestingWidget", field="serial"))],
        expected_errors=[],
        expected_lookup_calls=[{"old"}],
    ),
    ResolveCase(
        name="absent_attribute_unknown_id",
        submitted=[
            SchemaRoot(nodes=[_widget("n1", attributes=[_attribute("serial", "zzz", state=HashableModelState.ABSENT)])])
        ],
        existing_ids=set(),
        expected_ids={"TestingWidget": "n1", "TestingWidget.serial": None},
        expected_absent_removed=[],
        expected_warnings=[_ignored_warning(SchemaWarningKind(kind="TestingWidget", field="serial"))],
        expected_errors=[],
        expected_lookup_calls=[{"zzz"}],
    ),
    ResolveCase(
        name="absent_node_id_in_database",
        submitted=[
            SchemaRoot(
                nodes=[
                    _widget("old", attributes=[_attribute("serial", "zzz")], state=HashableModelState.ABSENT),
                    NodeSchema(id="n2", name="Gadget", namespace="Testing"),
                ]
            )
        ],
        existing_ids={"old"},
        expected_ids={"TestingGadget": "n2"},
        expected_absent_removed=["TestingWidget", "TestingWidget.serial"],
        expected_warnings=[_skipped_warning(SchemaWarningKind(kind="TestingWidget", field=None))],
        expected_errors=[],
        expected_lookup_calls=[{"old", "zzz"}],
    ),
    ResolveCase(
        name="absent_node_id_in_database_with_stored_field_id",
        submitted=[
            SchemaRoot(
                nodes=[_widget("old", attributes=[_attribute("serial", "n2a")], state=HashableModelState.ABSENT)]
            )
        ],
        existing_ids={"old"},
        expected_ids={},
        expected_absent_removed=["TestingWidget", "TestingWidget.serial"],
        expected_warnings=[_skipped_warning(SchemaWarningKind(kind="TestingWidget", field=None))],
        expected_errors=[],
        expected_lookup_calls=[{"old"}],
    ),
    ResolveCase(
        name="absent_node_field_repeats_an_earlier_id",
        submitted=[
            SchemaRoot(
                nodes=[
                    NodeSchema(id="n2", name="Gadget", namespace="Testing", attributes=[_attribute("serial", "n2a")]),
                    _widget("old", attributes=[_attribute("serial_copy", "n2a")], state=HashableModelState.ABSENT),
                ]
            )
        ],
        existing_ids={"old"},
        expected_ids={"TestingGadget": "n2", "TestingGadget.serial": "n2a"},
        expected_absent_removed=["TestingWidget", "TestingWidget.serial_copy"],
        expected_warnings=[_skipped_warning(SchemaWarningKind(kind="TestingWidget", field=None))],
        expected_errors=["TestingWidget.serial_copy: id 'n2a' is also given to attribute 'TestingGadget.serial'"],
        expected_lookup_calls=[{"old"}],
    ),
    ResolveCase(
        name="absent_generic_id_in_database",
        submitted=[
            SchemaRoot(
                generics=[GenericSchema(id="old", name="Thing", namespace="Testing", state=HashableModelState.ABSENT)]
            )
        ],
        existing_ids={"old"},
        expected_ids={},
        expected_absent_removed=["TestingThing"],
        expected_warnings=[_skipped_warning(SchemaWarningKind(kind="TestingThing", field=None))],
        expected_errors=[],
        expected_lookup_calls=[{"old"}],
    ),
    ResolveCase(
        name="ignored_and_skipped_warnings_together",
        submitted=[
            SchemaRoot(
                nodes=[
                    _widget(
                        "n1",
                        attributes=[_attribute("serial", "zzz")],
                        relationships=[_relationship("parts", "old", state=HashableModelState.ABSENT)],
                    )
                ]
            )
        ],
        existing_ids={"old"},
        expected_ids={"TestingWidget": "n1", "TestingWidget.serial": None},
        expected_absent_removed=["TestingWidget.parts"],
        expected_warnings=[
            _ignored_warning(SchemaWarningKind(kind="TestingWidget", field="serial")),
            _skipped_warning(SchemaWarningKind(kind="TestingWidget", field="parts")),
        ],
        expected_errors=[],
        expected_lookup_calls=[{"zzz", "old"}],
    ),
    ResolveCase(
        name="attribute_id_of_other_node",
        submitted=[SchemaRoot(nodes=[_widget("n1", attributes=[_attribute("serial", "n2a")])])],
        existing_ids=set(),
        expected_ids={"TestingWidget": "n1", "TestingWidget.serial": "n2a"},
        expected_absent_removed=[],
        expected_warnings=[],
        expected_errors=["TestingWidget.serial: id 'n2a' belongs to attribute 'TestingGadget.serial'"],
        expected_lookup_calls=[],
    ),
    ResolveCase(
        name="attribute_id_of_relationship",
        submitted=[SchemaRoot(nodes=[_widget("n1", attributes=[_attribute("serial", "n1r")])])],
        existing_ids=set(),
        expected_ids={"TestingWidget": "n1", "TestingWidget.serial": "n1r"},
        expected_absent_removed=[],
        expected_warnings=[],
        expected_errors=["TestingWidget.serial: id 'n1r' belongs to relationship 'TestingWidget.parts'"],
        expected_lookup_calls=[],
    ),
    ResolveCase(
        name="node_id_of_generic",
        submitted=[SchemaRoot(nodes=[_widget("g1")])],
        existing_ids=set(),
        expected_ids={"TestingWidget": "g1"},
        expected_absent_removed=[],
        expected_warnings=[],
        expected_errors=["TestingWidget: id 'g1' belongs to generic 'TestingThing'"],
        expected_lookup_calls=[],
    ),
    ResolveCase(
        name="generic_attribute_id_on_inheriting_node",
        submitted=[SchemaRoot(nodes=[_widget("n1", attributes=[_attribute("label", "g1a")])])],
        existing_ids=set(),
        expected_ids={"TestingWidget": "n1", "TestingWidget.label": "g1a"},
        expected_absent_removed=[],
        expected_warnings=[],
        expected_errors=["TestingWidget.label: id 'g1a' belongs to attribute 'TestingThing.label'"],
        expected_lookup_calls=[],
    ),
    ResolveCase(
        name="extension_attribute_unknown_id",
        submitted=[
            SchemaRoot(
                extensions=SchemaExtension(
                    nodes=[NodeExtensionSchema(kind="TestingWidget", attributes=[_attribute("extra", "zzz")])]
                )
            )
        ],
        existing_ids=set(),
        expected_ids={"TestingWidget.extra": None},
        expected_absent_removed=[],
        expected_warnings=[_ignored_warning(SchemaWarningKind(kind="TestingWidget", field="extra"))],
        expected_errors=[],
        expected_lookup_calls=[{"zzz"}],
    ),
    ResolveCase(
        name="same_node_in_two_files",
        submitted=[
            SchemaRoot(nodes=[_widget(None, attributes=[_attribute("serial", "zzz")])]),
            SchemaRoot(nodes=[_widget(None, attributes=[_attribute("serial", "zzz")])]),
        ],
        existing_ids=set(),
        expected_ids={"TestingWidget": None, "TestingWidget.serial": None},
        expected_absent_removed=[],
        expected_warnings=[
            _ignored_warning(
                SchemaWarningKind(kind="TestingWidget", field="serial"),
                SchemaWarningKind(kind="TestingWidget", field="serial"),
            )
        ],
        expected_errors=[],
        expected_lookup_calls=[{"zzz"}],
    ),
    ResolveCase(
        name="rename_with_extension_field_ids",
        submitted=[
            SchemaRoot(
                nodes=[_widget("n1", name="Renamed")],
                extensions=SchemaExtension(
                    nodes=[NodeExtensionSchema(kind="TestingRenamed", attributes=[_attribute("serial", "n1a")])]
                ),
            )
        ],
        existing_ids=set(),
        expected_ids={"TestingRenamed": "n1", "TestingRenamed.serial": "n1a"},
        expected_absent_removed=[],
        expected_warnings=[],
        expected_errors=[],
        expected_lookup_calls=[],
    ),
    ResolveCase(
        name="rename_in_one_file_fields_in_another",
        submitted=[
            SchemaRoot(nodes=[_widget("n1", name="Renamed")]),
            SchemaRoot(nodes=[_widget(None, name="Renamed", attributes=[_attribute("serial", "n1a")])]),
        ],
        existing_ids=set(),
        expected_ids={"TestingRenamed": "n1", "TestingRenamed.serial": "n1a"},
        expected_absent_removed=[],
        expected_warnings=[],
        expected_errors=[],
        expected_lookup_calls=[],
    ),
    ResolveCase(
        name="two_nodes_with_one_id",
        submitted=[SchemaRoot(nodes=[_widget("n1"), _widget("n1", name="Other")])],
        existing_ids=set(),
        expected_ids={"TestingWidget": "n1", "TestingOther": "n1"},
        expected_absent_removed=[],
        expected_warnings=[],
        expected_errors=["TestingOther: id 'n1' is also given to node 'TestingWidget'"],
        expected_lookup_calls=[],
    ),
    ResolveCase(
        name="two_attributes_with_one_id",
        submitted=[
            SchemaRoot(
                nodes=[_widget("n1", attributes=[_attribute("serial", "n1a"), _attribute("serial_copy", "n1a")])]
            )
        ],
        existing_ids=set(),
        expected_ids={"TestingWidget": "n1", "TestingWidget.serial": "n1a", "TestingWidget.serial_copy": "n1a"},
        expected_absent_removed=[],
        expected_warnings=[],
        expected_errors=["TestingWidget.serial_copy: id 'n1a' is also given to attribute 'TestingWidget.serial'"],
        expected_lookup_calls=[],
    ),
    ResolveCase(
        name="extension_repeats_node_field",
        submitted=[
            SchemaRoot(
                nodes=[_widget("n1", attributes=[_attribute("serial", "n1a")])],
                extensions=SchemaExtension(
                    nodes=[NodeExtensionSchema(kind="TestingWidget", attributes=[_attribute("serial", "n1a")])]
                ),
            )
        ],
        existing_ids=set(),
        expected_ids={"TestingWidget": "n1", "TestingWidget.serial": "n1a"},
        expected_absent_removed=[],
        expected_warnings=[],
        expected_errors=[],
        expected_lookup_calls=[],
    ),
    ResolveCase(
        name="unknown_id_on_two_elements",
        submitted=[
            SchemaRoot(nodes=[_widget("n1", attributes=[_attribute("serial", "zzz"), _attribute("color", "zzz")])])
        ],
        existing_ids=set(),
        expected_ids={"TestingWidget": "n1", "TestingWidget.serial": None, "TestingWidget.color": "zzz"},
        expected_absent_removed=[],
        expected_warnings=[_ignored_warning(SchemaWarningKind(kind="TestingWidget", field="serial"))],
        expected_errors=["TestingWidget.color: id 'zzz' is also given to attribute 'TestingWidget.serial'"],
        expected_lookup_calls=[{"zzz"}],
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in RESOLVE_CASES])
async def test_resolve(stored_branch_schema: SchemaBranch, test_case: ResolveCase) -> None:
    lookup = InMemorySchemaElementIdLookup(existing_ids=test_case.existing_ids)
    resolver = SubmittedSchemaIdResolver(lookup=lookup)

    resolution = await resolver.resolve(branch_schema=stored_branch_schema, schemas=test_case.submitted)

    resolved_ids = _element_ids(resolution.schemas)
    assert resolved_ids == test_case.expected_ids
    assert [
        label for label in _element_ids(test_case.submitted) if label not in resolved_ids
    ] == test_case.expected_absent_removed
    assert resolution.warnings == test_case.expected_warnings
    assert resolution.errors == test_case.expected_errors
    assert lookup.calls == test_case.expected_lookup_calls


async def test_input_is_not_modified(stored_branch_schema: SchemaBranch) -> None:
    submitted = [
        SchemaRoot(
            nodes=[
                _widget(
                    "n1",
                    attributes=[_attribute("serial", "zzz")],
                    relationships=[_relationship("parts", "old", state=HashableModelState.ABSENT)],
                )
            ]
        )
    ]
    resolver = SubmittedSchemaIdResolver(lookup=InMemorySchemaElementIdLookup(existing_ids={"old"}))

    await resolver.resolve(branch_schema=stored_branch_schema, schemas=submitted)

    assert _element_ids(submitted) == {
        "TestingWidget": "n1",
        "TestingWidget.serial": "zzz",
        "TestingWidget.parts": "old",
    }


async def test_roots_without_ids_are_returned_unchanged(stored_branch_schema: SchemaBranch) -> None:
    submitted = [
        SchemaRoot(
            nodes=[
                _widget(None, attributes=[_attribute("serial", None)], relationships=[_relationship("parts", None)])
            ],
            extensions=SchemaExtension(
                nodes=[NodeExtensionSchema(kind="TestingWidget", attributes=[_attribute("extra", None)])]
            ),
        )
    ]
    lookup = InMemorySchemaElementIdLookup(existing_ids=set())
    resolver = SubmittedSchemaIdResolver(lookup=lookup)

    resolution = await resolver.resolve(branch_schema=stored_branch_schema, schemas=submitted)

    assert len(resolution.schemas) == len(submitted)
    assert all(resolved is original for resolved, original in zip(resolution.schemas, submitted, strict=True))
    assert resolution.warnings == []
    assert resolution.errors == []
    assert lookup.calls == []
