from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

import pytest

from infrahub.core.graphql_query.node_id_query import NodeIDQuery
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot
from tests.helpers.schema import WIDGET, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator


class TestNodeIDQueryPaging(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def widget_ids(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        default_branch: Branch,
        bus_simulator: BusSimulator,
    ) -> list[str]:
        widget_schema = deepcopy(WIDGET)
        widget_schema.order_by = ["height__value"]
        await load_schema(db, schema=SchemaRoot(nodes=[widget_schema]), update_db=True)
        widget_ids = []
        for height in range(4):
            widget = await Node.init(db=db, schema=WIDGET.kind)
            await widget.new(db=db, name=f"widget-{height}", height=height)
            await widget.save(db=db)
            widget_ids.append(widget.id)
        return widget_ids

    async def test_paging_returns_every_node_once_when_the_sort_field_changes_between_pages(
        self,
        db: InfrahubDatabase,
        widget_ids: list[str],
        default_branch: Branch,
        client: InfrahubClient,
    ) -> None:
        """Rewriting the schema order_by field of already-paged nodes neither repeats nor skips a node."""
        pages = NodeIDQuery(kind=WIDGET.kind).fetch_all_paginated(
            client=client, branch_name=default_branch.name, page_size=2
        )
        paged_ids = await anext(pages)

        # Sorted by height, moving the first page's nodes last would put them back under the next offset.
        for position, widget_id in enumerate(paged_ids):
            widget = await NodeManager.get_one(db=db, id=widget_id, raise_on_error=True)
            widget.get_attribute(name="height").value = 10 + position
            await widget.save(db=db)

        async for page in pages:
            paged_ids.extend(page)

        assert sorted(paged_ids) == sorted(widget_ids)
