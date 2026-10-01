from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fast_depends import dependency_provider

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.display_labels.tasks import trigger_update_display_labels
from infrahub.workflows.catalogue import DISPLAY_LABELS_PROCESS_JINJA2
from infrahub.workflows.constants import WorkflowTag
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.test_app import TestInfrahubApp
from tests.helpers.workflow_override import override_workflow

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.events.models import EventContext
    from tests.adapters.message_bus import BusSimulator


class TestDisplayLabelTaskOptimization(TestInfrahubApp):
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
        for name in ["alpha", "beta", "gamma"]:
            tag = await Node.init(db=db, schema=InfrahubKind.TAG)
            await tag.new(db=db, name=name)
            await tag.save(db=db)
            tag_ids.append(tag.id)
        return tag_ids

    async def test_trigger_update_display_labels_submits_bounded_batches_covering_all_nodes(
        self,
        db: InfrahubDatabase,
        tags_dataset: list[str],
        default_branch: Branch,
        client: InfrahubClient,
        context: EventContext,
        prefect_test_fixture: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A kind-wide backfill submits one process flow per chunk of nodes, each carrying the branch tag.

        Branch-filtered task queries match on that tag, and only creation tags reliably
        survive in-flow tag updates.
        """
        # Limit 4 -> chunk size 2, so three nodes already split into [2, 1].
        monkeypatch.setenv("PREFECT_SERVER_EVENTS_MAXIMUM_RELATED_RESOURCES", "4")
        # The default pagination size would return all three ids in one page, leaving paging between chunks untested.
        monkeypatch.setattr(client.config, "pagination_size", 2)

        recorder = WorkflowRecorder()
        with override_workflow(recorder, dependency_provider=dependency_provider):
            await trigger_update_display_labels(
                branch_name=default_branch.name,
                kind=InfrahubKind.TAG,
                context=context,
            )

        submissions = recorder.get_submit_calls_for(DISPLAY_LABELS_PROCESS_JINJA2)
        assert [len(call["parameters"]["object_ids"]) for call in submissions] == [2, 1]

        submitted_ids = [oid for call in submissions for oid in call["parameters"]["object_ids"]]
        assert sorted(submitted_ids) == sorted(tags_dataset)

        branch_tag = WorkflowTag.BRANCH.render(identifier=default_branch.name)
        assert all(branch_tag in call["tags"] for call in submissions)
