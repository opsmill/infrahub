from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

import pytest

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from infrahub.display_labels.tasks import process_display_label
from tests.helpers.schema import WIDGET, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.events.models import EventContext
    from tests.adapters.message_bus import BusSimulator


def _widget_schema(display_label: str) -> SchemaRoot:
    widget = deepcopy(WIDGET)
    widget.display_label = display_label
    return SchemaRoot(nodes=[widget])


class TestDisplayLabelRenderFailure(TestInfrahubApp):
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
    async def widget_ids(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        default_branch: Branch,
        bus_simulator: BusSimulator,
    ) -> dict[str, str]:
        await load_schema(db, schema=_widget_schema(display_label="{{ name__value }}"), update_db=True)
        widget_ids = {}
        for name, height in [("alpha", 4), ("beta", 5), ("gamma", None)]:
            widget = await Node.init(db=db, schema=WIDGET.kind)
            await widget.new(db=db, name=name, height=height)
            await widget.save(db=db)
            widget_ids[name] = widget.id

        # Dividing by the null height of "gamma" raises, so only that node fails to render.
        await load_schema(
            db, schema=_widget_schema(display_label="{{ name__value }}/{{ 100 // height__value }}"), update_db=True
        )
        return widget_ids

    async def test_process_display_label_skips_only_the_node_whose_template_raises(
        self,
        db: InfrahubDatabase,
        widget_ids: dict[str, str],
        default_branch: Branch,
        client: InfrahubClient,
        context: EventContext,
        prefect_test_fixture: None,
    ) -> None:
        """The failing node keeps its stored label and the rest of the batch gets the new one."""
        await process_display_label(
            branch_name=default_branch.name,
            node_kind=WIDGET.kind,
            target_kind=WIDGET.kind,
            object_ids=list(widget_ids.values()),
            context=context,
        )

        labels = {}
        for name, widget_id in widget_ids.items():
            widget = await NodeManager.get_one(db=db, id=widget_id, raise_on_error=True)
            labels[name] = await widget.get_display_label(db=db)
        assert labels == {"alpha": "alpha/25", "beta": "beta/20", "gamma": "gamma"}
