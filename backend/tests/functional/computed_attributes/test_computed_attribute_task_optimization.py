from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fast_depends import dependency_provider

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.computed_attribute.tasks import (
    trigger_update_jinja2_computed_attributes,
    trigger_update_python_computed_attributes,
)
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.workers.dependencies import build_workflow
from infrahub.workflows.catalogue import (
    COMPUTED_ATTRIBUTE_PROCESS_JINJA2,
    COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM,
)
from infrahub.workflows.constants import WorkflowTag
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.events.models import EventContext
    from tests.adapters.message_bus import BusSimulator


class TestComputedAttributeTaskOptimization(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def context(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        default_branch: Branch,
    ) -> EventContext:
        admin_account = await NodeManager.get_one_by_hfid(
            db=db, kind=InfrahubKind.ACCOUNT, hfid=["admin"], raise_on_error=True
        )
        return InfrahubContext(
            account=AccountSession(authenticated=True, account_id=admin_account.id, auth_type=AuthType.API),
            branch=BranchContext(name=default_branch.name, id=str(default_branch.uuid)),
        ).to_event_context()

    @pytest.fixture(scope="class")
    async def tags_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        default_branch: Branch,
        bus_simulator: BusSimulator,
    ) -> list[str]:
        tag_ids = []
        for name in ["ca-alpha", "ca-beta", "ca-gamma"]:
            tag = await Node.init(db=db, schema=InfrahubKind.TAG)
            await tag.new(db=db, name=name)
            await tag.save(db=db)
            tag_ids.append(tag.id)
        return tag_ids

    async def test_trigger_update_jinja2_computed_attributes_submits_all_node_ids(
        self,
        db: InfrahubDatabase,
        tags_dataset: list[str],
        default_branch: Branch,
        client: InfrahubClient,
        context: EventContext,
        prefect_test_fixture: None,
    ) -> None:
        recorder = WorkflowRecorder()
        with dependency_provider.scope(build_workflow, lambda: recorder):
            await trigger_update_jinja2_computed_attributes(
                branch_name=default_branch.name,
                computed_attribute_name="test-attribute",
                computed_attribute_kind=InfrahubKind.TAG,
                context=context,
            )

        submitted_ids = {
            call["parameters"]["object_id"] for call in recorder.get_submit_calls_for(COMPUTED_ATTRIBUTE_PROCESS_JINJA2)
        }
        assert submitted_ids == set(tags_dataset)

    async def test_trigger_update_python_computed_attributes_chunks_and_tags_submissions(
        self,
        db: InfrahubDatabase,
        tags_dataset: list[str],
        default_branch: Branch,
        client: InfrahubClient,
        context: EventContext,
        prefect_test_fixture: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An oversized fan-out splits into bounded submissions, each carrying the branch tag.

        Branch-filtered task queries match on that tag, and only creation tags reliably
        survive in-flow tag updates.
        """
        # Limit 4 -> chunk size 2, so three nodes already split into [2, 1].
        monkeypatch.setenv("PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES", "4")

        recorder = WorkflowRecorder()
        with dependency_provider.scope(build_workflow, lambda: recorder):
            await trigger_update_python_computed_attributes(
                branch_name=default_branch.name,
                computed_attribute_name="test-attribute",
                computed_attribute_kind=InfrahubKind.TAG,
                context=context,
            )

        submissions = recorder.get_submit_calls_for(COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM)
        assert [len(call["parameters"]["object_ids"]) for call in submissions] == [2, 1]

        submitted_ids = [oid for call in submissions for oid in call["parameters"]["object_ids"]]
        assert sorted(submitted_ids) == sorted(tags_dataset)

        branch_tag = WorkflowTag.BRANCH.render(identifier=default_branch.name)
        assert all(branch_tag in call["tags"] for call in submissions)
