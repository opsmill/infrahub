from __future__ import annotations

from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING

import pytest

from infrahub import lock
from infrahub.computed_attribute.tasks import computed_attribute_setup_python
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema
from infrahub.events.schema_action import ChangedElementsPayload
from infrahub.git.writeback.models import HeldPythonAttribute, HeldRegeneration, PendingMerge
from infrahub.git.writeback.store import WritebackIntentStore
from infrahub.workflows.catalogue import TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES
from tests.component.computed_attribute._base import (
    CAR_PERSON_PYTHON_SCHEMA,
    ScopedRecomputeCase,
    ScopedRecomputeTestBase,
    commit_schema_branch,
    create_transform01,
)
from tests.helpers.schema import load_schema

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.core.protocols import CoreAccount
    from infrahub.database import InfrahubDatabase
    from tests.adapters.workflow import WorkflowRecorder


# ``computed_desc_python`` reads only TestCar.name via transform01.
# ``computed_desc_python_opaque`` reads display_label via transform_opaque. The fields behind
# that label cannot be named, so any change to TestCar recomputes it, while a change to a kind
# its query never reaches does not. That holds because TestCar's label is built from its own
# attributes; a label crossing a relationship recomputes on any schema change instead.
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
    ScopedRecomputeCase(
        name="unread_kind_skips_scoped_and_opaque",
        changed_elements=ChangedElementsPayload(changed_fields={"TestPerson": ["name"]}),
        expected_submitted=set(),
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
        repo = await create_transform01(db=db, branch_name=default_branch.name)

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

    async def test_a_schema_altered_branch_recomputes_what_it_shares_with_main(
        self,
        db: InfrahubDatabase,
        transform_dataset: None,
        workflow_recorder: WorkflowRecorder,
        admin_account: CoreAccount,
    ) -> None:
        """A schema change on a branch recomputes the attributes the branch shares with main.

        The branch declares no computed attribute of its own. Its candidates are the owner
        automations scoped to it, and it has those only because its schema hash differs from the
        default branch. The attribute it shares reads TestCar.name, so the same change that
        selects it on main selects it here.
        """
        branch = await create_branch(branch_name="branch_alters_schema", db=db)

        branch_schema = registry.schema.get_schema_branch(name=branch.name)
        person_schema = branch_schema.get_node("TestPerson")
        person_schema.attributes.append(AttributeSchema(name="nickname", kind="Text", optional=True))
        branch_schema.set(name="TestPerson", schema=person_schema)
        await commit_schema_branch(db=db, branch=branch, schema_branch=branch_schema)

        # The premise: without this the branch owns no automation and the flow below has nothing
        # to select, which would pass for the wrong reason.
        assert branch.name in registry.get_altered_schema_branches()

        await computed_attribute_setup_python(
            context=self._context(admin_account, branch),
            branch_name=branch.name,
            changed_elements=ChangedElementsPayload(changed_fields={"TestCar": ["name"]}),
        )

        assert self._submitted_attribute_names(workflow_recorder) == {
            "computed_desc_python",
            "computed_desc_python_opaque",
        }


class TestScopedRecomputePythonOfAPendingRepository(ScopedRecomputeTestBase):
    """A repository whose merges wait for their push holds the recompute of the attributes its transforms compute."""

    WORKFLOW = TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES

    @pytest.fixture(scope="class")
    async def delivery_state(self, db: InfrahubDatabase, default_branch: Branch) -> WritebackIntentStore:
        return WritebackIntentStore(
            db=db, lock_registry=lock.registry, default_branch=default_branch, clock=partial(datetime.now, UTC)
        )

    @pytest.fixture(scope="class")
    async def pending_repository_id(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        admin_account: CoreAccount,
        delivery_state: WritebackIntentStore,
    ) -> str:
        """Compute one attribute with a read-only repository, and the other with a repository that waits for its push."""
        await create_transform01(db=db, branch_name=default_branch.name)

        query_opaque = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
        await query_opaque.new(
            db=db,
            name="query_opaque",
            query="query { TestCar { edges { node { display_label } } } }",
            models=["TestCar"],
        )
        await query_opaque.save(db=db)

        pending_repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
        await pending_repository.new(db=db, name="pending-repository", location="pending-location", commit="commit02")
        await pending_repository.save(db=db)

        transform_opaque = await Node.init(db=db, schema=InfrahubKind.TRANSFORMPYTHON)
        await transform_opaque.new(
            db=db,
            name="transform_opaque",
            file_path="transform.py",
            class_name="Transform",
            query=query_opaque,
            repository=pending_repository,
        )
        await transform_opaque.save(db=db)

        await load_schema(db=db, schema=CAR_PERSON_PYTHON_SCHEMA, update_db=True)
        await delivery_state.enqueue(
            repository_id=pending_repository.id,
            entry=PendingMerge(
                entry_id="pending-merge",
                source_branch="feature",
                source_git_branch="feature",
                source_commit="0123456789abcdef0123456789abcdef01234567",
                merged_at=datetime.now(UTC),
            ),
            widen=False,
        )
        return pending_repository.id

    async def test_the_attribute_of_the_pending_repository_waits_for_its_delivery(
        self,
        pending_repository_id: str,
        delivery_state: WritebackIntentStore,
        workflow_recorder: WorkflowRecorder,
        default_branch: Branch,
        admin_account: CoreAccount,
    ) -> None:
        await computed_attribute_setup_python(
            context=self._context(admin_account, default_branch),
            branch_name=default_branch.name,
            changed_elements=ChangedElementsPayload(changed_fields={"TestCar": ["name"]}),
        )

        assert self._submitted_attribute_names(workflow_recorder) == {"computed_desc_python"}
        intent = await delivery_state.read(repository_id=pending_repository_id)
        assert intent.held == HeldRegeneration(
            next_hold_seq=2,
            python_attributes=(
                HeldPythonAttribute(kind="TestCar", attribute="computed_desc_python_opaque", hold_seq=1),
            ),
        )
