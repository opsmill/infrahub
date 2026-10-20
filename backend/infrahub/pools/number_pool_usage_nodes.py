"""The nodes the dedicated number-pool queries name: the peers of scope elements and the objects holding numbers."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from infrahub.core.manager import NodeManager
from infrahub.pools.number_pool_usage import HoldingObject, PeerSummary

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.branch import Branch
    from infrahub.core.query.resource_manager import NumberPoolAllocatedResult
    from infrahub.database import InfrahubDatabase


class PeerSummaryReader:
    """Reads the display label and kind of scope element peers, on any branch."""

    def __init__(self, db: InfrahubDatabase, branch: Branch) -> None:
        self.db = db
        self.branch = branch

    async def read(self, ids: set[str]) -> dict[str, PeerSummary]:
        """Return the summary of each peer that can be read, by peer id."""
        if not ids:
            return {}
        nodes = await NodeManager.get_many(db=self.db, ids=sorted(ids), branch=self.branch, branch_agnostic=True)
        return {
            node_id: PeerSummary(display_label=await node.get_display_label(db=self.db), kind=node.get_kind())
            for node_id, node in nodes.items()
        }


class HoldingObjectReader:
    """Reads the objects holding tracked numbers, each on the branch where it holds its number."""

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def read(self, rows: Sequence[NumberPoolAllocatedResult], kind: str) -> dict[tuple[str, str], HoldingObject]:
        """Return each row's holding object by branch and id, with one read per branch.

        An object that cannot be read on its branch is reported with `kind` and its id as display label.
        """
        ids_by_branch: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            ids_by_branch[row.branch].add(row.id)
        holders: dict[tuple[str, str], HoldingObject] = {}
        for branch_name, ids in ids_by_branch.items():
            nodes = await NodeManager.get_many(db=self.db, ids=sorted(ids), branch=branch_name)
            for node_id in ids:
                node = nodes.get(node_id)
                holders[branch_name, node_id] = (
                    HoldingObject(
                        id=node_id,
                        hfid=await node.get_hfid(db=self.db),
                        kind=node.get_kind(),
                        display_label=await node.get_display_label(db=self.db),
                    )
                    if node is not None
                    else HoldingObject(id=node_id, hfid=None, kind=kind, display_label=node_id)
                )
        return holders
