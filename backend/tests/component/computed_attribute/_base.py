"""Shared fixtures, helpers, and parametrize case shape for scoped recompute tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, AsyncGenerator, ClassVar, Generator

import pytest

from infrahub import config
from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import InfrahubContext
from infrahub.core.constants import InfrahubKind, RelationshipCardinality
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.computed_attribute import ComputedAttribute, ComputedAttributeKind
from infrahub.events.schema_action import ChangedElementsPayload  # noqa: TC001  used in dataclass field
from infrahub.server import app
from infrahub.workers.dependencies import build_workflow
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.task_manager import setup_task_manager_once
from tests.helpers.test_app import TestInfrahubAppBase

if TYPE_CHECKING:
    from fast_depends import Provider

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from infrahub.events.models import EventContext
    from infrahub.services import InfrahubServices
    from infrahub.workflows.models import WorkflowDefinition


# Two Python computed attributes on TestCar, each fed by its own transform (transform01 and
# transform_opaque), with a Person peer. TestCar's display label is built from its own name, so a
# transform reading that label can be scoped to TestCar; a label crossing a relationship could not.
CAR_PERSON_PYTHON_SCHEMA = SchemaRoot(
    nodes=[
        NodeSchema(
            name="Car",
            namespace="Test",
            display_labels=["name__value"],
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


async def create_transform01(db: InfrahubDatabase, branch_name: str) -> Node:
    """query01/repo01/transform01: a Python transform whose query reads only TestCar.name.

    The edges/node query structure is required for the analyzer to record the field as
    a read, making ``name`` the single "related" field. Returns the repository so a
    test can attach further transforms to it.
    """
    query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
    await query.new(
        db=db,
        name="query01",
        query="query TestCarQuery($id: ID!) { TestCar(ids: [$id]) { edges { node { name { value } } } } }",
        models=["TestCar", "TestPerson"],
    )
    await query.save(db=db)

    repo = await Node.init(db=db, schema=InfrahubKind.READONLYREPOSITORY)
    await repo.new(db=db, name="repo01", ref=branch_name, commit="commit01", location="location01", queries=[query])
    await repo.save(db=db)

    transform = await Node.init(db=db, schema=InfrahubKind.TRANSFORMPYTHON)
    await transform.new(
        db=db, name="transform01", file_path="transform.py", class_name="Transform", query=query, repository=repo
    )
    await transform.save(db=db)

    return repo


@dataclass
class ScopedRecomputeCase:
    """A single ``(changed_elements -> expected submitted set)`` parametrize case."""

    name: str
    changed_elements: ChangedElementsPayload | None
    expected_submitted: set[str]


class ScopedRecomputeTestBase(TestInfrahubAppBase):
    """Fixtures and helpers shared by the Jinja2 and Python scoped recompute tests.

    Subclasses set ``WORKFLOW`` to the recompute trigger workflow whose submissions
    are being recorded.
    """

    WORKFLOW: ClassVar[WorkflowDefinition]

    @pytest.fixture(scope="class", autouse=True)
    async def workflow_recorder(
        self,
        prefect: Generator[str, None, None],
        dependency_provider: Provider,
    ) -> AsyncGenerator[WorkflowRecorder, None]:
        original = config.OVERRIDE.workflow
        recorder = WorkflowRecorder()
        await setup_task_manager_once()
        config.OVERRIDE.workflow = recorder
        with dependency_provider.scope(build_workflow, lambda: recorder):
            yield recorder
        config.OVERRIDE.workflow = original

    @pytest.fixture(scope="class", autouse=True)
    async def service(self, test_client: Any) -> InfrahubServices:
        return app.state.service

    @pytest.fixture(autouse=True)
    def clear_recorder(self, workflow_recorder: WorkflowRecorder) -> None:
        workflow_recorder.reset()

    @staticmethod
    def _context(admin_account: CoreAccount, branch: Branch) -> EventContext:
        account = AccountSession(auth_type=AuthType.JWT, authenticated=True, account_id=admin_account.id)
        return InfrahubContext.init(branch=branch, account=account).to_event_context()

    def _submitted_attribute_names(self, recorder: WorkflowRecorder) -> set[str]:
        return {call["parameters"]["computed_attribute_name"] for call in recorder.get_submit_calls_for(self.WORKFLOW)}
