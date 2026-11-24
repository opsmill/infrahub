"""The cases that the session loads together over one base, each in its own namespace.

A case joins the combined load only when its change raises nothing during the direct load, the build and the apply.
"""

from infrahub.core.constants import RelationshipDeleteBehavior, RelationshipKind
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from tests.constants import TestKind
from tests.unit.core.schema_change.equivalence_cases_fields import FIELD_EQUIVALENCE_CASES
from tests.unit.core.schema_change.equivalence_cases_kinds import KIND_EQUIVALENCE_CASES, rename_attribute_on_generic
from tests.unit.core.schema_change.equivalence_cases_relationships import RELATIONSHIP_EQUIVALENCE_CASES
from tests.unit.core.schema_change.helpers import (
    DEVICE_SPARE_SFPS_RELATIONSHIP,
    INTERFACE_KINDS,
    CaseScope,
    CombinedLoadCase,
)

EQUIVALENCE_CASES: list[CombinedLoadCase] = [
    *KIND_EQUIVALENCE_CASES,
    *RELATIONSHIP_EQUIVALENCE_CASES,
    *FIELD_EQUIVALENCE_CASES,
]


def _turn_unique_off(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    device = scope.node(TestKind.DEVICE)
    device.get_attribute(name="name").unique = False
    return SchemaRoot(nodes=[device])


def _change_relationship_to_component(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    device = scope.node(TestKind.DEVICE)
    device.get_relationship(name=DEVICE_SPARE_SFPS_RELATIONSHIP).kind = RelationshipKind.COMPONENT
    return SchemaRoot(nodes=[device])


def _change_relationship_to_component_with_on_delete(scope: CaseScope, _: SchemaBranch) -> SchemaRoot:
    device = scope.node(TestKind.DEVICE)
    spare_sfps = device.get_relationship(name=DEVICE_SPARE_SFPS_RELATIONSHIP)
    spare_sfps.kind = RelationshipKind.COMPONENT
    spare_sfps.on_delete = RelationshipDeleteBehavior.NO_ACTION
    return SchemaRoot(nodes=[device])


TURN_UNIQUE_OFF = CombinedLoadCase(
    name="turn_unique_off", namespace="Uniqueoff", base_kinds=INTERFACE_KINDS, schema_file=_turn_unique_off
)
CHANGE_RELATIONSHIP_TO_COMPONENT = CombinedLoadCase(
    name="change_relationship_to_component",
    namespace="Cascade",
    base_kinds=INTERFACE_KINDS,
    schema_file=_change_relationship_to_component,
)
CHANGE_RELATIONSHIP_TO_COMPONENT_WITH_ON_DELETE = CombinedLoadCase(
    name="change_relationship_to_component_with_on_delete",
    namespace="Noaction",
    base_kinds=INTERFACE_KINDS,
    schema_file=_change_relationship_to_component_with_on_delete,
)
RENAME_ATTRIBUTE_ON_GENERIC_WITH_PROFILES = CombinedLoadCase(
    name="rename_attribute_on_generic_with_profiles",
    namespace="Inheritedrename",
    base_kinds=INTERFACE_KINDS,
    schema_file=rename_attribute_on_generic,
)

KNOWN_BUG_CASES: list[CombinedLoadCase] = [
    TURN_UNIQUE_OFF,
    CHANGE_RELATIONSHIP_TO_COMPONENT,
    CHANGE_RELATIONSHIP_TO_COMPONENT_WITH_ON_DELETE,
    RENAME_ATTRIBUTE_ON_GENERIC_WITH_PROFILES,
]
"""Cases whose result the known-bug tests read.

The check of each case leaves them out, because a known bug can leave the diff of a case empty.
"""

COMBINED_LOAD_CASES: list[CombinedLoadCase] = [*EQUIVALENCE_CASES, *KNOWN_BUG_CASES]
