from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.computed_attribute.tasks import computed_attribute_setup_python
from infrahub.core.constants import InfrahubKind, RelationshipCardinality
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.computed_attribute import ComputedAttribute, ComputedAttributeKind
from infrahub.events.schema_action import ChangedElementsPayload
from infrahub.workflows.catalogue import TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES
from tests.component.computed_attribute._base import ScopedRecomputeCase, ScopedRecomputeTestBase
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.adapters.workflow import WorkflowRecorder


CAR_PERSON_PYTHON_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="Car",
            namespace="Test",
            attributes=[
                AttributeSchema(name="name", kind="Text", unique=True),
                AttributeSchema(name="nbr_seats", kind="Number", optional=True),
                AttributeSchema(
                    name="computed_desc_python",
                    kind="Text",
                    read_only=True,
                    optional=True,
                    computed_attribute=ComputedAttribute(
                        kind=ComputedAttributeKind.TRANSFORM_PYTHON,
                        transform="transform01",
                    ),
                ),
                AttributeSchema(
                    name="computed_desc_python_opaque",
                    kind="Text",
                    read_only=True,
                    optional=True,
                    computed_attribute=ComputedAttribute(
                        kind=ComputedAttributeKind.TRANSFORM_PYTHON,
                        transform="transform_opaque",
                    ),
                ),
            ],
            relationships=[
                RelationshipSchema(
                    name="owner",
                    peer="TestPerson",
                    optional=False,
                    cardinality=RelationshipCardinality.ONE,
                ),
            ],
        ),
        NodeSchema(
            name="Person",
            namespace="Test",
            attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
            relationships=[
                RelationshipSchema(name="cars", peer="TestCar", cardinality=RelationshipCardinality.MANY),
            ],
        ),
    ]
)


# ``computed_desc_python`` reads only TestCar.name via transform01.
# ``computed_desc_python_opaque`` reads display_label via transform_opaque, so its read set
# is imprecise and the attribute always recomputes (the conservative, opaque case).
PYTHON_CASES = [
    ScopedRecomputeCase(
        name="unrelated_field_skips_scoped_keeps_opaque",
        changed_elements=ChangedElementsPayload(changed_fields={"TestCar": ["nbr_seats"]}),
        expected_submitted={"computed_desc_python_opaque"},
    ),
    ScopedRecomputeCase(
        name="related_field_recomputes_scoped_and_opaque",
        changed_elements=ChangedElementsPayload(changed_fields={"TestCar": ["name"]}),
        expected_submitted={"computed_desc_python", "computed_desc_python_opaque"},
    ),
]


class TestScopedRecomputePython(ScopedRecomputeTestBase):
    WORKFLOW = TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES

    @pytest.fixture(scope="class")
    async def transform_dataset(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        admin_account: CoreAccount,
    ) -> None:
        # The transform query reads only TestCar.name, so that is the single "related" field.
        # The edges/node structure is required for the analyzer to record the field as a read.
        query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
        await query.new(
            db=db,
            name="query01",
            query="query { TestCar { edges { node { name { value } } } } }",
            models=["TestCar", "TestPerson"],
        )
        await query.save(db=db)

        repo = await Node.init(db=db, schema=InfrahubKind.READONLYREPOSITORY)
        await repo.new(
            db=db, name="repo01", ref=default_branch.name, commit="commit01", location="location01", queries=[query]
        )
        await repo.save(db=db)

        transform = await Node.init(db=db, schema=InfrahubKind.TRANSFORMPYTHON)
        await transform.new(
            db=db, name="transform01", file_path="transform.py", class_name="Transform", query=query, repository=repo
        )
        await transform.save(db=db)

        # A query reading the display label cannot be mapped to precise backing fields,
        # so its attribute is always recomputed (the conservative, opaque case).
        query_opaque = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
        await query_opaque.new(
            db=db,
            name="query_opaque",
            query="query { TestCar { edges { node { display_label } } } }",
            models=["TestCar"],
        )
        await query_opaque.save(db=db)

        transform_opaque = await Node.init(db=db, schema=InfrahubKind.TRANSFORMPYTHON)
        await transform_opaque.new(
            db=db,
            name="transform_opaque",
            file_path="transform.py",
            class_name="Transform",
            query=query_opaque,
            repository=repo,
        )
        await transform_opaque.save(db=db)

        await load_schema(db=db, schema=CAR_PERSON_PYTHON_SCHEMA, update_db=True)

    @pytest.mark.parametrize("case", PYTHON_CASES, ids=[c.name for c in PYTHON_CASES])
    async def test_scoped_recompute(
        self,
        case: ScopedRecomputeCase,
        transform_dataset: None,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        await computed_attribute_setup_python(
            context=self._context(admin_account, default_branch),
            branch_name=default_branch.name,
            changed_elements=case.changed_elements,
        )
        assert self._submitted_attribute_names(workflow_recorder) == case.expected_submitted
