from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncGenerator, Generator

import pytest

from infrahub import config
from infrahub.auth import AccountSession, AuthType
from infrahub.computed_attribute.tasks import computed_attribute_setup_python
from infrahub.context import InfrahubContext
from infrahub.core.constants import InfrahubKind, RelationshipCardinality
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.computed_attribute import ComputedAttribute, ComputedAttributeKind
from infrahub.events.schema_action import ChangedElementsPayload
from infrahub.server import app
from infrahub.workers.dependencies import build_workflow
from infrahub.workflows.catalogue import TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES
from infrahub.workflows.initialization import setup_task_manager
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.schema import load_schema
from tests.helpers.test_app import TestInfrahubAppBase

if TYPE_CHECKING:
    from fast_depends import Provider
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices


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


class TestScopedRecomputePython(TestInfrahubAppBase):
    @pytest.fixture(scope="class", autouse=True)
    async def workflow_recorder(
        self,
        prefect: Generator[str, None, None],
        dependency_provider: Provider,
    ) -> AsyncGenerator[WorkflowRecorder, None]:
        original = config.OVERRIDE.workflow
        recorder = WorkflowRecorder()
        await setup_task_manager()
        config.OVERRIDE.workflow = recorder
        with dependency_provider.scope(build_workflow, lambda: recorder):
            yield recorder
        config.OVERRIDE.workflow = original

    @pytest.fixture(scope="class", autouse=True)
    async def service(self, test_client: Any) -> InfrahubServices:
        return app.state.service

    @pytest.fixture(autouse=True)
    def clear_recorder(self, workflow_recorder: WorkflowRecorder) -> None:
        workflow_recorder.execute_calls.clear()
        workflow_recorder.submit_calls.clear()

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

    def _context(self, admin_account: CoreAccount, branch: Branch) -> InfrahubContext:
        account = AccountSession(auth_type=AuthType.JWT, authenticated=True, account_id=admin_account.id, role="admin")
        return InfrahubContext.init(branch=branch, account=account)

    @staticmethod
    def _submitted_attribute_names(recorder: WorkflowRecorder) -> set[str]:
        return {
            call["parameters"]["computed_attribute_name"]
            for call in recorder.get_submit_calls_for(TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES)
        }

    async def test_unrelated_change_skips_scoped_python_recompute(
        self,
        transform_dataset: None,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        client: InfrahubClient,
    ) -> None:
        """A change to a field no transform reads does not recompute the precisely-scoped attribute."""
        context = self._context(admin_account, default_branch)
        changed_elements = ChangedElementsPayload(changed_fields={"TestCar": ["nbr_seats"]})

        await computed_attribute_setup_python(
            context=context,
            branch_name=default_branch.name,
            changed_elements=changed_elements,
        )

        assert "computed_desc_python" not in self._submitted_attribute_names(workflow_recorder)

    async def test_related_change_submits_python_recompute(
        self,
        transform_dataset: None,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        client: InfrahubClient,
    ) -> None:
        """A change to a field the transform reads (TestCar.name) submits the recompute job."""
        context = self._context(admin_account, default_branch)
        changed_elements = ChangedElementsPayload(changed_fields={"TestCar": ["name"]})

        await computed_attribute_setup_python(
            context=context,
            branch_name=default_branch.name,
            changed_elements=changed_elements,
        )

        assert "computed_desc_python" in self._submitted_attribute_names(workflow_recorder)

    async def test_opaque_attribute_recomputed_without_full_escalation(
        self,
        transform_dataset: None,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
        client: InfrahubClient,
    ) -> None:
        """An unanalyzable-query attribute recomputes on an unrelated change while a scoped one is skipped.

        Proves the opaque attribute does not escalate to a branch-wide full recompute.
        """
        context = self._context(admin_account, default_branch)
        changed_elements = ChangedElementsPayload(changed_fields={"TestCar": ["nbr_seats"]})

        await computed_attribute_setup_python(
            context=context,
            branch_name=default_branch.name,
            changed_elements=changed_elements,
        )

        submitted = self._submitted_attribute_names(workflow_recorder)
        assert "computed_desc_python_opaque" in submitted
        assert "computed_desc_python" not in submitted
