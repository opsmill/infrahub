"""The nodes the dedicated number-pool queries name: the peers of scope elements and the objects holding numbers."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Protocol

from infrahub.core.constants import MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.pools.number_pool_usage import HoldingObject, NumberHolder, PeerSummary

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class HeldRow(Protocol):
    """An object holding a number, and a branch it holds it on."""

    @property
    def id(self) -> str: ...

    @property
    def branch(self) -> str: ...


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


class NumberHolderNodeReader:
    """Reads an object holding numbers: its label and the pools tracking them."""

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def read(self, node_id: str, attribute_names: Sequence[str], branch: Branch) -> NumberHolder | None:
        """Return the object and the pools tracking its attributes, or None when it cannot be read on `branch`."""
        node = await NodeManager.get_one(
            db=self.db, id=node_id, branch=branch, include_metadata=MetadataOptions.TRACKING_POOL
        )
        if node is None:
            return None
        if node.get_schema().display_label:
            label = await node.get_display_label(db=self.db) or None
        else:
            hfid = await node.get_hfid(db=self.db)
            label = ", ".join(hfid) if hfid else None
        tracking_pool_ids: dict[str, str] = {}
        for attribute_name in attribute_names:
            if attribute_name not in node.get_schema().attribute_names:
                continue
            tracking_pool = node.get_attribute(name=attribute_name).tracking_pool
            if tracking_pool is not None:
                tracking_pool_ids[attribute_name] = tracking_pool.pool_id
        return NumberHolder(label=label, tracking_pool_ids=tracking_pool_ids)


class HoldingObjectReader:
    """Reads the objects holding tracked numbers, each on the branch where it holds its number."""

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def read(self, rows: Sequence[HeldRow], kind: str) -> dict[tuple[str, str], HoldingObject]:
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
