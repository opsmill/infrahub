from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import DiffAction
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.ownership.models import NODE_SOURCES_HOLDER
from infrahub.database.validation import verify_graph
from tests.helpers.ownership import (
    SOURCES_FIELD,
    OwnerDataset,
    add_node,
    read_owners,
    set_owners,
)

from ..get_one_node import get_one_diff_node
from ._ownership import merge, update_diff

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.diff.model.path import EnrichedDiffProperty, EnrichedDiffRoot
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.database import InfrahubDatabase


async def _set_sources(db: InfrahubDatabase, branch: Branch, node_id: str, source_ids: tuple[str, ...] | None) -> None:
    await set_owners(db=db, branch=branch, node_id=node_id, owner_ids=source_ids, holder=NODE_SOURCES_HOLDER)


async def _read_sources(db: InfrahubDatabase, branch: Branch, node_id: str) -> tuple[str, ...] | None:
    return await read_owners(db=db, branch=branch, node_id=node_id, holder=NODE_SOURCES_HOLDER)


def _sources_property(diff: EnrichedDiffRoot, node_id: str) -> EnrichedDiffProperty:
    node = get_one_diff_node(diff_root=diff, node_uuid=node_id)
    return node.get_attribute(name=SOURCES_FIELD).get_property(property_type=DatabaseEdgeType.HAS_SOURCE)


async def test_two_sources_set_on_a_branch_show_on_the_default_branch_after_the_merge(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    sources = dataset.owners(("dc-emea", "network-emea"))
    owners = dataset.owners(("dc-emea",))
    await set_owners(db=db, branch=default_branch, node_id=tenant_id, owner_ids=owners)
    branch = await create_branch(db=db, branch_name="sources-merge")

    await _set_sources(db=db, branch=branch, node_id=tenant_id, source_ids=sources)

    assert await _read_sources(db=db, branch=branch, node_id=tenant_id) == sources
    assert await _read_sources(db=db, branch=default_branch, node_id=tenant_id) is None
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    changed = _sources_property(diff=diff, node_id=tenant_id)
    assert (changed.previous_value, changed.new_value, changed.action) == (
        None,
        dataset.owner_list(("dc-emea", "network-emea")),
        DiffAction.ADDED,
    )
    assert changed.new_label == dataset.owner_labels(("dc-emea", "network-emea"))
    assert [attribute.name for attribute in get_one_diff_node(diff_root=diff, node_uuid=tenant_id).attributes] == [
        SOURCES_FIELD
    ]

    await merge(db=db, branch=branch)

    assert await _read_sources(db=db, branch=default_branch, node_id=tenant_id) == sources
    assert await read_owners(db=db, branch=default_branch, node_id=tenant_id) == owners
    await verify_graph(db=db)


async def test_source_deleted_on_a_branch_stays_a_source_after_the_merge(
    db: InfrahubDatabase, default_branch: Branch, diff_repository: DiffRepository, dataset: OwnerDataset
) -> None:
    tenant_id = dataset.ids["tenant-a"]
    template = await add_node(db=db, kind="TemplateTestSite", template_name="emea-site")
    await _set_sources(db=db, branch=default_branch, node_id=tenant_id, source_ids=(template.id,))
    branch = await create_branch(db=db, branch_name="source-deleted")
    branch_template = await NodeManager.get_one(db=db, branch=branch, id=template.id, raise_on_error=True)

    await branch_template.delete(db=db)

    assert await _read_sources(db=db, branch=branch, node_id=tenant_id) == (template.id,)
    await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    await merge(db=db, branch=branch)

    assert await NodeManager.get_one(db=db, branch=default_branch, id=template.id) is None
    assert await _read_sources(db=db, branch=default_branch, node_id=tenant_id) == (template.id,)
    await verify_graph(db=db)
