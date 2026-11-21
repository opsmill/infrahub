from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

import pytest

from infrahub.computed_attribute.tasks import computed_attribute_setup_jinja2
from infrahub.core.constants import RelationshipCardinality
from infrahub.core.initialization import create_branch
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.computed_attribute import ComputedAttribute, ComputedAttributeKind
from infrahub.events import BranchDeletedEvent
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


# The same schema with another local_tag template: a branch loading it owns its schema, keeps the
# default branch template for local_label and remote_label, and diverges on local_tag.
JINJA2_SCHEMA_DIVERGING_TAG = deepcopy(JINJA2_SCHEMA)
JINJA2_SCHEMA_DIVERGING_TAG.nodes[1].get_attribute(name="local_tag").computed_attribute = ComputedAttribute(
    kind=ComputedAttributeKind.JINJA2,
    jinja2_template="{{ name__value }}/{{ role__value }}",
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

    async def test_deleted_branch_event_submits_nothing(
        self,
        jinja2_dataset: None,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        await computed_attribute_setup_jinja2(
            context=self._context(admin_account, default_branch),
            branch_name=default_branch.name,
            event_name=BranchDeletedEvent.event_name,
            changed_elements=None,
        )
        assert self._submitted(workflow_recorder) == set()

    async def test_branch_not_owning_its_schema_submits_nothing(
        self,
        db: InfrahubDatabase,
        jinja2_dataset: None,
        workflow_recorder: WorkflowRecorder,
        admin_account: CoreAccount,
    ) -> None:
        branch = await create_branch(branch_name="same-schema", db=db)

        await computed_attribute_setup_jinja2(
            context=self._context(admin_account, branch),
            branch_name=branch.name,
            changed_elements=None,
        )
        assert self._submitted(workflow_recorder) == set()

    async def test_diverging_branch_submits_only_attributes_whose_template_differs(
        self,
        db: InfrahubDatabase,
        jinja2_dataset: None,
        workflow_recorder: WorkflowRecorder,
        admin_account: CoreAccount,
    ) -> None:
        branch = await create_branch(branch_name="diverging-tag", db=db)
        await load_schema(db=db, schema=JINJA2_SCHEMA_DIVERGING_TAG, branch_name=branch.name, update_db=True)

        await computed_attribute_setup_jinja2(
            context=self._context(admin_account, branch),
            branch_name=branch.name,
            changed_elements=None,
        )
        assert self._submitted(workflow_recorder) == {("diverging-tag", "local_tag")}

    @staticmethod
    def _submitted(recorder: WorkflowRecorder) -> set[tuple[str, str]]:
        return {
            (call["parameters"]["branch_name"], call["parameters"]["computed_attribute_name"])
            for call in recorder.get_submit_calls_for(TRIGGER_UPDATE_JINJA_COMPUTED_ATTRIBUTES)
        }
