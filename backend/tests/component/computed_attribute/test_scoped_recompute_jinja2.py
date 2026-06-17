from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.computed_attribute.tasks import computed_attribute_setup_jinja2
from infrahub.core.constants import RelationshipCardinality
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.computed_attribute import ComputedAttribute, ComputedAttributeKind
from infrahub.events.schema_action import ChangedElementsPayload
from infrahub.workflows.catalogue import TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES
from tests.component.computed_attribute._base import ScopedRecomputeCase, ScopedRecomputeTestBase
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.adapters.workflow import WorkflowRecorder


# local_label / local_tag read local fields (name / role); remote_label reads the owner
# peer's name across the relationship.
JINJA2_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="ComputeOwner",
            namespace="Test",
            attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
        ),
        NodeSchema(
            name="ComputeDevice",
            namespace="Test",
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="role", kind="Text"),
                AttributeSchema(name="description", kind="Text", optional=True),
                AttributeSchema(
                    name="local_label",
                    kind="Text",
                    read_only=True,
                    computed_attribute=ComputedAttribute(
                        kind=ComputedAttributeKind.JINJA2,
                        jinja2_template="{{ name__value }}-{{ role__value }}",
                    ),
                ),
                AttributeSchema(
                    name="local_tag",
                    kind="Text",
                    optional=True,
                    read_only=True,
                    computed_attribute=ComputedAttribute(
                        kind=ComputedAttributeKind.JINJA2,
                        jinja2_template="{{ role__value }}:{{ name__value }}",
                    ),
                ),
                AttributeSchema(
                    name="remote_label",
                    kind="Text",
                    read_only=True,
                    computed_attribute=ComputedAttribute(
                        kind=ComputedAttributeKind.JINJA2,
                        jinja2_template="{{ owner__name__value }}'s {{ name__value }}",
                    ),
                ),
            ],
            relationships=[
                RelationshipSchema(
                    name="owner",
                    peer="TestComputeOwner",
                    optional=False,
                    cardinality=RelationshipCardinality.ONE,
                ),
            ],
        ),
    ]
)


JINJA2_CASES = [
    ScopedRecomputeCase(
        name="unrelated_field_change_submits_nothing",
        changed_elements=ChangedElementsPayload(changed_fields={"TestComputeDevice": ["description"]}),
        expected_submitted=set(),
    ),
    ScopedRecomputeCase(
        name="relationship_peer_field_change_recomputes_remote_label",
        changed_elements=ChangedElementsPayload(changed_fields={"TestComputeOwner": ["name"]}),
        expected_submitted={"remote_label"},
    ),
    ScopedRecomputeCase(
        name="local_role_change_recomputes_both_local_attributes",
        changed_elements=ChangedElementsPayload(changed_fields={"TestComputeDevice": ["role"]}),
        expected_submitted={"local_label", "local_tag"},
    ),
    ScopedRecomputeCase(
        name="own_definition_change_recomputes_self",
        changed_elements=ChangedElementsPayload(changed_fields={"TestComputeDevice": ["local_label"]}),
        expected_submitted={"local_label"},
    ),
    ScopedRecomputeCase(
        name="no_change_set_falls_back_to_every_attribute",
        changed_elements=None,
        expected_submitted={"local_label", "local_tag", "remote_label"},
    ),
]


class TestScopedRecomputeJinja2(ScopedRecomputeTestBase):
    WORKFLOW = TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES

    @pytest.fixture(scope="class")
    async def jinja2_dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        admin_account: CoreAccount,
    ) -> None:
        await load_schema(db=db, schema=JINJA2_SCHEMA, update_db=True)

    @pytest.mark.parametrize("case", JINJA2_CASES, ids=[c.name for c in JINJA2_CASES])
    async def test_scoped_recompute(
        self,
        case: ScopedRecomputeCase,
        jinja2_dataset: None,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        await computed_attribute_setup_jinja2(
            context=self._context(admin_account, default_branch),
            branch_name=default_branch.name,
            changed_elements=case.changed_elements,
        )
        assert self._submitted_attribute_names(workflow_recorder) == case.expected_submitted
