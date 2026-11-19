"""Diff, merge and rebase of each holder of owners, for the same scenarios.

Each test runs one scenario on the holders that no other test of this package covers for that scenario.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.changelog.builder import build_diff_changelog_collector
from infrahub.core.constants import DiffAction, MetadataOptions
from infrahub.core.constants.database import DatabaseEdgeType
from infrahub.core.diff.model.path import ConflictSelection
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.node.create import create_node
from infrahub.core.ownership.models import (
    NODE_HOLDER,
    NODE_SOURCES_HOLDER,
    NODE_TARGET_HOLDER,
    HolderKey,
    HolderKind,
    field_holder,
)
from infrahub.core.ownership.repository import OwnershipRepository
from infrahub.core.timestamp import Timestamp
from infrahub.database.validation import verify_graph
from infrahub.exceptions import ValidationError
from tests.helpers.ownership import (
    OWNERS_FIELD,
    SOURCES_FIELD,
    TARGET_OWNERS_FIELD,
    OwnerDataset,
    load_owner_dataset,
    read_owners,
    set_owners,
)

from ..get_one_node import get_one_diff_node
from ._ownership import (
    count_active_holder_edges,
    holder_edges,
    merge,
    profile_with_device,
    rebase_with_conflict_check,
    update_diff,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fast_depends import Provider

    from infrahub.core.changelog.models import NodeChangelog
    from infrahub.core.diff.model.path import EnrichedDiffProperty, EnrichedDiffRoot
    from infrahub.core.diff.repository.repository import DiffRepository
    from infrahub.database import InfrahubDatabase
    from tests.adapters.cache import MemoryCache
    from tests.adapters.workflow import WorkflowRecorder

Names = tuple[str, ...] | None
"""Group names. None is inherit, an empty tuple is "no owner"."""

Changelog = tuple[str, Any, Any]
"""The name of the changed field or property, its previous value and its new value."""


@pytest.fixture
async def dataset(db: InfrahubDatabase, default_branch: Branch) -> OwnerDataset:
    return await load_owner_dataset(db=db, default_branch=default_branch)


def _field(kind: str, field_name: str, target: bool = False) -> HolderKey:
    schema = registry.schema.get(name=kind, branch=registry.default_branch, duplicate=False)
    holder = field_holder(schema=schema, field_name=field_name, target=target)
    assert holder is not None
    return holder


class OwnerListHolder:
    """A list of owners that the owner writer replaces as a whole."""

    single = False
    """True when the holder keeps one owner at most."""

    no_owner = True
    """True when the holder can store the "no owner" state."""

    property_type = DatabaseEdgeType.HAS_OWNER

    def __init__(self, name: str, node_name: str, field_name: str, holder: HolderKey | tuple[str, str, bool]) -> None:
        self.name = name
        self.node_name = node_name
        self.field_name = field_name
        self._holder = holder

    def __repr__(self) -> str:
        return self.name

    @property
    def holder(self) -> HolderKey:
        if isinstance(self._holder, HolderKey):
            return self._holder
        return _field(*self._holder)

    async def prepare(self, db: InfrahubDatabase, default_branch: Branch, dataset: OwnerDataset, start: Names) -> str:
        """Write the first state on the default branch and return the ID of the node of the holder."""
        node_id = dataset.ids[self.node_name]
        await self.write(db=db, branch=default_branch, dataset=dataset, node_id=node_id, names=start)
        return node_id

    async def write(
        self, db: InfrahubDatabase, branch: Branch, dataset: OwnerDataset, node_id: str, names: Names
    ) -> None:
        await set_owners(db=db, branch=branch, node_id=node_id, owner_ids=dataset.owners(names), holder=self.holder)

    async def read(self, db: InfrahubDatabase, branch: Branch, node_id: str) -> tuple[str, ...] | None:
        return await read_owners(db=db, branch=branch, node_id=node_id, holder=self.holder)

    def diff_property(self, diff: EnrichedDiffRoot, node_id: str) -> EnrichedDiffProperty:
        node = get_one_diff_node(diff_root=diff, node_uuid=node_id)
        return node.get_attribute(name=self.field_name).get_property(property_type=self.property_type)

    def diff_value(self, dataset: OwnerDataset, names: Names) -> str | None:
        return dataset.owner_list(names)

    def changelog(self, changelogs: Sequence[tuple[DiffAction, NodeChangelog]], node_id: str) -> Changelog | None:
        attributes = _changelog_of(changelogs=changelogs, node_id=node_id).get("attributes", {})
        if self.field_name not in attributes:
            return None
        entry = attributes[self.field_name]
        return (self.field_name, entry["value_previous"], entry["value"])

    def expected_changelog(self, dataset: OwnerDataset, before: Names, after: Names) -> Changelog:
        return (self.field_name, dataset.owner_list(before), dataset.owner_list(after))


class SourcesHolder(OwnerListHolder):
    no_owner = False
    property_type = DatabaseEdgeType.HAS_SOURCE


class ProfileHolder(OwnerListHolder):
    """Owners that a device profile gives. A device of the rack `rack-a` uses the profile."""

    async def prepare(self, db: InfrahubDatabase, default_branch: Branch, dataset: OwnerDataset, start: Names) -> str:
        profile_id, _ = await profile_with_device(db=db, dataset=dataset)
        await self.write(db=db, branch=default_branch, dataset=dataset, node_id=profile_id, names=start)
        return profile_id


class TemplateCopyHolder(OwnerListHolder):
    """Own owners of a site, which start as a copy of the owners that its object template gives."""

    async def prepare(self, db: InfrahubDatabase, default_branch: Branch, dataset: OwnerDataset, start: Names) -> str:
        assert start is not None, "a template that inherits gives no owners to copy"
        template = await Node.init(db=db, schema="TemplateTestSite")
        await template.new(db=db, template_name="emea-site")
        await template.save(db=db)
        await set_owners(
            db=db,
            branch=default_branch,
            node_id=template.id,
            owner_ids=dataset.owners(start),
            holder=NODE_TARGET_HOLDER,
        )
        site = await create_node(
            data={"name": "site-a", "object_template": {"id": template.id}},
            db=db,
            branch=default_branch,
            schema=registry.schema.get_node_schema(name="TestSite", branch=default_branch),
        )
        stored = await OwnershipRepository(db=db, branch=default_branch, at=None).read(node_ids=[site.id])
        assert stored[site.id].get(NODE_HOLDER).template_id == template.id
        return site.id


class AttributeOwnersHolder(OwnerListHolder):
    """Own owners of the attribute `name`, which the changelog records as a property of the attribute."""

    def changelog(self, changelogs: Sequence[tuple[DiffAction, NodeChangelog]], node_id: str) -> Changelog | None:
        attribute = _changelog_of(changelogs=changelogs, node_id=node_id).get("attributes", {}).get("name")
        properties = {} if attribute is None else attribute["properties"]
        if not properties:
            return None
        assert len(properties) == 1, properties
        name, entry = next(iter(properties.items()))
        return (name, entry["value_previous"], entry["value"])

    def expected_changelog(self, dataset: OwnerDataset, before: Names, after: Names) -> Changelog:
        if all(names is None or len(names) == 1 for names in (before, after)):
            ids = [None if names is None else dataset.ids[names[0]] for names in (before, after)]
            return ("owner", ids[0], ids[1])
        return ("owners", dataset.owner_list(before), dataset.owner_list(after))


class AttributeOwnerPropertyHolder(AttributeOwnersHolder):
    """The `owner` property of the attribute `name`, written by the save of the node."""

    single = True
    no_owner = False

    async def write(
        self, db: InfrahubDatabase, branch: Branch, dataset: OwnerDataset, node_id: str, names: Names
    ) -> None:
        node = await NodeManager.get_one(
            db=db, branch=branch, id=node_id, include_metadata=MetadataOptions.OWNER, raise_on_error=True
        )
        if names:
            node.get_attribute(name="name").owner = dataset.ids[names[0]]
        else:
            node.get_attribute(name="name").clear_owner()
        await node.save(db=db)


class LinkOwnerHolder(OwnerListHolder):
    """The `owner` property of the link from the device `device-a` to the rack `rack-a`."""

    single = True
    no_owner = False

    async def _link(self, db: InfrahubDatabase, branch: Branch, node_id: str) -> tuple[Node, Any]:
        node = await NodeManager.get_one(
            db=db, branch=branch, id=node_id, include_metadata=MetadataOptions.OWNER, raise_on_error=True
        )
        links = await node.get_relationship(name="rack").get_relationships(db=db)
        assert len(links) == 1
        return node, links[0]

    async def write(
        self, db: InfrahubDatabase, branch: Branch, dataset: OwnerDataset, node_id: str, names: Names
    ) -> None:
        node, link = await self._link(db=db, branch=branch, node_id=node_id)
        if names:
            link.owner = dataset.ids[names[0]]
        else:
            link.clear_owner()
        await node.save(db=db)

    async def read(self, db: InfrahubDatabase, branch: Branch, node_id: str) -> tuple[str, ...] | None:
        _, link = await self._link(db=db, branch=branch, node_id=node_id)
        return None if link.owner_id is None else (str(link.owner_id),)

    def diff_property(self, diff: EnrichedDiffRoot, node_id: str) -> EnrichedDiffProperty:
        relationship = get_one_diff_node(diff_root=diff, node_uuid=node_id).get_relationship(name="rack")
        assert len(relationship.relationships) == 1
        link = next(iter(relationship.relationships))
        return link.get_property(property_type=DatabaseEdgeType.HAS_OWNER)

    def diff_value(self, dataset: OwnerDataset, names: Names) -> str | None:
        return dataset.ids[names[0]] if names else None

    def changelog(self, changelogs: Sequence[tuple[DiffAction, NodeChangelog]], node_id: str) -> Changelog | None:
        relationship = _changelog_of(changelogs=changelogs, node_id=node_id).get("relationships", {}).get("rack")
        entry = None if relationship is None else relationship["properties"].get("owner")
        return None if entry is None else ("owner", entry["value_previous"], entry["value"])

    def expected_changelog(self, dataset: OwnerDataset, before: Names, after: Names) -> Changelog:
        return ("owner", self.diff_value(dataset=dataset, names=before), self.diff_value(dataset=dataset, names=after))


def _changelog_of(changelogs: Sequence[tuple[DiffAction, NodeChangelog]], node_id: str) -> dict[str, Any]:
    matching = [changelog.model_dump() for _, changelog in changelogs if changelog.node_id == node_id]
    assert len(matching) <= 1
    return matching[0] if matching else {}


NODE = OwnerListHolder(name="node", node_name="tenant-a", field_name=OWNERS_FIELD, holder=NODE_HOLDER)
ATTRIBUTE = AttributeOwnersHolder(
    name="attribute",
    node_name="tenant-a",
    field_name="name",
    holder=HolderKey(kind=HolderKind.ATTRIBUTE, attribute="name"),
)
RELATIONSHIP_ONE = OwnerListHolder(
    name="relationship_of_cardinality_one",
    node_name="device-a",
    field_name="rack__owners",
    holder=("TestDevice", "rack", False),
)
RELATIONSHIP_MANY = OwnerListHolder(
    name="relationship_of_cardinality_many",
    node_name="rack-a",
    field_name="children__owners",
    holder=("TestRack", "children", False),
)
PROFILE = ProfileHolder(name="profile", node_name="", field_name=TARGET_OWNERS_FIELD, holder=NODE_TARGET_HOLDER)
PROFILE_ATTRIBUTE = ProfileHolder(
    name="profile_attribute",
    node_name="",
    field_name="name__target_owners",
    holder=("TestDevice", "name", True),
)
PROFILE_RELATIONSHIP = ProfileHolder(
    name="profile_relationship",
    node_name="",
    field_name="rack__target_owners",
    holder=("TestDevice", "rack", True),
)
TEMPLATE_COPY = TemplateCopyHolder(name="template_copy", node_name="", field_name=OWNERS_FIELD, holder=NODE_HOLDER)
SOURCES = SourcesHolder(name="sources", node_name="tenant-a", field_name=SOURCES_FIELD, holder=NODE_SOURCES_HOLDER)
ATTRIBUTE_OWNER_PROPERTY = AttributeOwnerPropertyHolder(
    name="attribute_owner_property",
    node_name="tenant-a",
    field_name="name",
    holder=HolderKey(kind=HolderKind.ATTRIBUTE, attribute="name"),
)
LINK_OWNER_PROPERTY = LinkOwnerHolder(
    name="link_owner_property", node_name="device-a", field_name="rack", holder=NODE_HOLDER
)

# The owner code does not read the cardinality of a relationship field, so only the conflict scenario holds both.
ALL_HOLDERS = [
    NODE,
    ATTRIBUTE,
    RELATIONSHIP_ONE,
    PROFILE,
    PROFILE_ATTRIBUTE,
    PROFILE_RELATIONSHIP,
    TEMPLATE_COPY,
    SOURCES,
    ATTRIBUTE_OWNER_PROPERTY,
    LINK_OWNER_PROPERTY,
]

START: Names = ("dc-emea",)
OTHER: Names = ("security",)


def _branch_change(holder: OwnerListHolder) -> Names:
    return ("network-emea",) if holder.single else ("dc-emea", "network-emea")


def _params(holders: list[OwnerListHolder]) -> list[Any]:
    return [pytest.param(holder, id=holder.name) for holder in holders]


def _edge_count(names: Names) -> int:
    """Return the number of active owner edges that a holder needs for this state."""
    if names is None:
        return 0
    return len(names) or 1


async def _merge_changelogs(
    db: InfrahubDatabase, default_branch: Branch, branch: Branch, diff: EnrichedDiffRoot
) -> Sequence[tuple[DiffAction, NodeChangelog]]:
    """Merge the branch and return the changelogs that the merge of this diff records on the default branch."""
    merge_at = Timestamp()
    await merge(db=db, branch=branch, at=merge_at)
    return await build_diff_changelog_collector(
        diff=diff, db=db, branch=default_branch, merge_at=merge_at
    ).collect_changelogs()


S1_HOLDERS = [
    ATTRIBUTE,
    RELATIONSHIP_ONE,
    PROFILE,
    PROFILE_ATTRIBUTE,
    PROFILE_RELATIONSHIP,
    TEMPLATE_COPY,
    LINK_OWNER_PROPERTY,
]


@pytest.mark.parametrize("holder", _params(S1_HOLDERS))
async def test_owner_change_on_a_branch_is_merged_with_its_changelog(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    holder: OwnerListHolder,
) -> None:
    after = _branch_change(holder)
    node_id = await holder.prepare(db=db, default_branch=default_branch, dataset=dataset, start=START)
    branch = await create_branch(db=db, branch_name="owner-change")
    await holder.write(db=db, branch=branch, dataset=dataset, node_id=node_id, names=after)

    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    owners = holder.diff_property(diff=diff, node_id=node_id)
    assert (owners.previous_value, owners.new_value, owners.action, owners.conflict) == (
        holder.diff_value(dataset=dataset, names=START),
        holder.diff_value(dataset=dataset, names=after),
        DiffAction.UPDATED,
        None,
    )
    assert diff.get_all_conflicts() == {}

    changelogs = await _merge_changelogs(db=db, default_branch=default_branch, branch=branch, diff=diff)

    for read_branch in (default_branch, branch):
        assert await holder.read(db=db, branch=read_branch, node_id=node_id) == dataset.owners(after)
    assert await count_active_holder_edges(db=db, branch=default_branch, node_id=node_id) == _edge_count(after)
    assert holder.changelog(changelogs=changelogs, node_id=node_id) == holder.expected_changelog(
        dataset=dataset, before=START, after=after
    )
    await verify_graph(db=db)


async def _same_change_on_both_branches(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    holder: OwnerListHolder,
) -> tuple[str, Branch, EnrichedDiffRoot]:
    """Make the same owner change on the default branch and on a new branch, and return the node, the branch and its diff."""
    after = _branch_change(holder)
    node_id = await holder.prepare(db=db, default_branch=default_branch, dataset=dataset, start=START)
    branch = await create_branch(db=db, branch_name="same-change")
    await holder.write(db=db, branch=default_branch, dataset=dataset, node_id=node_id, names=after)
    await holder.write(db=db, branch=branch, dataset=dataset, node_id=node_id, names=after)
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    return node_id, branch, diff


@pytest.mark.parametrize("holder", _params(ALL_HOLDERS))
async def test_same_owner_change_on_both_branches_gives_no_conflict_and_the_merge_changes_nothing(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    holder: OwnerListHolder,
) -> None:
    after = _branch_change(holder)
    node_id, branch, diff = await _same_change_on_both_branches(
        db=db, default_branch=default_branch, diff_repository=diff_repository, dataset=dataset, holder=holder
    )

    owners = holder.diff_property(diff=diff, node_id=node_id)
    assert (owners.previous_value, owners.new_value, owners.action, owners.conflict) == (
        holder.diff_value(dataset=dataset, names=START),
        holder.diff_value(dataset=dataset, names=after),
        DiffAction.UPDATED,
        None,
    )
    assert diff.get_all_conflicts() == {}
    edges_before_merge = await holder_edges(db=db, branch=default_branch, node_id=node_id)

    await merge(db=db, branch=branch)

    assert await holder_edges(db=db, branch=default_branch, node_id=node_id) == edges_before_merge
    for read_branch in (default_branch, branch):
        assert await holder.read(db=db, branch=read_branch, node_id=node_id) == dataset.owners(after)
    await verify_graph(db=db)


@pytest.mark.parametrize(
    "holder",
    [
        *_params([holder for holder in ALL_HOLDERS if holder is not LINK_OWNER_PROPERTY]),
        pytest.param(
            LINK_OWNER_PROPERTY,
            id=LINK_OWNER_PROPERTY.name,
            marks=pytest.mark.xfail(strict=True, reason="develop behavior, tracked separately"),
        ),
    ],
)
async def test_merge_of_the_same_owner_change_on_both_branches_records_no_owner_change(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    holder: OwnerListHolder,
) -> None:
    node_id, branch, diff = await _same_change_on_both_branches(
        db=db, default_branch=default_branch, diff_repository=diff_repository, dataset=dataset, holder=holder
    )

    changelogs = await _merge_changelogs(db=db, default_branch=default_branch, branch=branch, diff=diff)

    assert holder.changelog(changelogs=changelogs, node_id=node_id) is None


S3_HOLDERS = [
    ATTRIBUTE,
    RELATIONSHIP_MANY,
    PROFILE_ATTRIBUTE,
    PROFILE_RELATIONSHIP,
    TEMPLATE_COPY,
    ATTRIBUTE_OWNER_PROPERTY,
    LINK_OWNER_PROPERTY,
]


def _selection_params() -> list[Any]:
    params = []
    for holder in S3_HOLDERS:
        for selection, name in (
            (ConflictSelection.DIFF_BRANCH, "branch_selected"),
            (ConflictSelection.BASE_BRANCH, "default_branch_selected"),
        ):
            marks = []
            if holder is LINK_OWNER_PROPERTY and selection is ConflictSelection.BASE_BRANCH:
                marks.append(
                    pytest.mark.xfail(
                        strict=True,
                        reason="the changelog of a link property ignores a selection of the default branch",
                    )
                )
            params.append(pytest.param(holder, selection, OTHER, id=f"{holder.name}-{name}", marks=marks))
            if holder is RELATIONSHIP_MANY:
                params.append(pytest.param(holder, selection, (), id=f"{holder.name}-{name}-no_owner_on_default"))
    return params


@pytest.mark.parametrize(("holder", "selection", "other"), _selection_params())
async def test_different_owner_changes_on_both_branches_conflict_and_the_merge_applies_the_selection(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    holder: OwnerListHolder,
    selection: ConflictSelection,
    other: Names,
) -> None:
    after = _branch_change(holder)
    node_id = await holder.prepare(db=db, default_branch=default_branch, dataset=dataset, start=START)
    branch = await create_branch(db=db, branch_name="different-change")
    await holder.write(db=db, branch=default_branch, dataset=dataset, node_id=node_id, names=other)
    await holder.write(db=db, branch=branch, dataset=dataset, node_id=node_id, names=after)

    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    owners = holder.diff_property(diff=diff, node_id=node_id)
    assert (owners.previous_value, owners.new_value) == (
        holder.diff_value(dataset=dataset, names=START),
        holder.diff_value(dataset=dataset, names=after),
    )
    conflict = owners.conflict
    assert conflict is not None
    assert (conflict.base_branch_value, conflict.diff_branch_value) == (
        holder.diff_value(dataset=dataset, names=other),
        holder.diff_value(dataset=dataset, names=after),
    )
    assert [found.uuid for found in diff.get_all_conflicts().values()] == [conflict.uuid]
    await diff_repository.update_conflict_by_id(conflict_id=conflict.uuid, selection=selection)
    diff = await diff_repository.get_one(diff_branch_name=branch.name, diff_id=diff.uuid)

    changelogs = await _merge_changelogs(db=db, default_branch=default_branch, branch=branch, diff=diff)

    merged = after if selection is ConflictSelection.DIFF_BRANCH else other
    assert await holder.read(db=db, branch=default_branch, node_id=node_id) == dataset.owners(merged)
    assert await holder.read(db=db, branch=branch, node_id=node_id) == dataset.owners(after)
    assert await count_active_holder_edges(db=db, branch=default_branch, node_id=node_id) == _edge_count(merged)
    assert holder.changelog(changelogs=changelogs, node_id=node_id) == (
        holder.expected_changelog(dataset=dataset, before=START, after=after)
        if selection is ConflictSelection.DIFF_BRANCH
        else None
    )
    await verify_graph(db=db)


@pytest.mark.parametrize("holder", _params([holder for holder in ALL_HOLDERS if holder is not NODE]))
async def test_rebase_refuses_different_owner_changes_on_both_branches(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    dependency_provider: Provider,
    memory_cache: MemoryCache,
    workflow_recorder: WorkflowRecorder,
    holder: OwnerListHolder,
) -> None:
    after = _branch_change(holder)
    node_id = await holder.prepare(db=db, default_branch=default_branch, dataset=dataset, start=START)
    branch = await create_branch(db=db, branch_name="rebase-conflict")
    await holder.write(db=db, branch=default_branch, dataset=dataset, node_id=node_id, names=OTHER)
    await holder.write(db=db, branch=branch, dataset=dataset, node_id=node_id, names=after)
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    conflict_paths = list(diff.get_all_conflicts())
    assert len(conflict_paths) == 1

    message = f"Update the data so that both branches agree on these conflicts: {conflict_paths[0]}."
    with pytest.raises(ValidationError, match=f"{re.escape(message)}$"):
        await rebase_with_conflict_check(
            db=db, default_branch=default_branch, branch=branch, dependency_provider=dependency_provider
        )

    assert (await Branch.get_by_name(db=db, name=branch.name)).branched_from == branch.branched_from
    assert await holder.read(db=db, branch=branch, node_id=node_id) == dataset.owners(after)
    assert await holder.read(db=db, branch=default_branch, node_id=node_id) == dataset.owners(OTHER)


@dataclass
class RemovalTestCase:
    name: str
    start: Names
    after: Names
    action: DiffAction


REMOVAL_TEST_CASES: list[RemovalTestCase] = [
    RemovalTestCase(
        name="owner_removed", start=("dc-emea", "network-emea"), after=("network-emea",), action=DiffAction.UPDATED
    ),
    RemovalTestCase(name="no_owner_set", start=("dc-emea",), after=(), action=DiffAction.UPDATED),
    RemovalTestCase(name="inherit_set", start=("dc-emea",), after=None, action=DiffAction.REMOVED),
    RemovalTestCase(name="no_owner_replaced", start=(), after=START, action=DiffAction.UPDATED),
]
S6_HOLDERS = [
    RELATIONSHIP_ONE,
    PROFILE_ATTRIBUTE,
    PROFILE_RELATIONSHIP,
    TEMPLATE_COPY,
    SOURCES,
    ATTRIBUTE_OWNER_PROPERTY,
    LINK_OWNER_PROPERTY,
]


def _removal_params() -> list[Any]:
    """Return the removal cases that each holder can store, except the source removal that another test covers."""
    params = []
    for holder in S6_HOLDERS:
        for test_case in REMOVAL_TEST_CASES:
            if () in (test_case.start, test_case.after) and not holder.no_owner:
                continue
            if test_case.name == "owner_removed" and (holder.single or holder is SOURCES):
                continue
            params.append(pytest.param(holder, test_case, id=f"{holder.name}-{test_case.name}"))
    return params


@pytest.mark.parametrize(("holder", "test_case"), _removal_params())
async def test_owner_removal_on_a_branch_is_merged(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    holder: OwnerListHolder,
    test_case: RemovalTestCase,
) -> None:
    node_id = await holder.prepare(db=db, default_branch=default_branch, dataset=dataset, start=test_case.start)
    branch = await create_branch(db=db, branch_name="owner-removal")
    await holder.write(db=db, branch=branch, dataset=dataset, node_id=node_id, names=test_case.after)

    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    owners = holder.diff_property(diff=diff, node_id=node_id)
    assert (owners.previous_value, owners.new_value, owners.action, owners.conflict) == (
        holder.diff_value(dataset=dataset, names=test_case.start),
        holder.diff_value(dataset=dataset, names=test_case.after),
        test_case.action,
        None,
    )

    changelogs = await _merge_changelogs(db=db, default_branch=default_branch, branch=branch, diff=diff)

    for read_branch in (default_branch, branch):
        assert await holder.read(db=db, branch=read_branch, node_id=node_id) == dataset.owners(test_case.after)
    assert await count_active_holder_edges(db=db, branch=default_branch, node_id=node_id) == _edge_count(
        test_case.after
    )
    assert holder.changelog(changelogs=changelogs, node_id=node_id) == holder.expected_changelog(
        dataset=dataset, before=test_case.start, after=test_case.after
    )
    await verify_graph(db=db)


@pytest.mark.parametrize(
    "holder",
    [
        *_params([holder for holder in ALL_HOLDERS if holder is not LINK_OWNER_PROPERTY]),
        pytest.param(
            LINK_OWNER_PROPERTY,
            id=LINK_OWNER_PROPERTY.name,
            marks=pytest.mark.xfail(strict=True, reason="the merge does not copy a link owner that is deleted"),
        ),
    ],
)
async def test_owner_added_on_a_branch_and_then_deleted_stays_in_the_owners_after_the_merge(
    db: InfrahubDatabase,
    default_branch: Branch,
    diff_repository: DiffRepository,
    dataset: OwnerDataset,
    holder: OwnerListHolder,
) -> None:
    after = _branch_change(holder)
    node_id = await holder.prepare(db=db, default_branch=default_branch, dataset=dataset, start=START)
    branch = await create_branch(db=db, branch_name="owner-deleted")
    await holder.write(db=db, branch=branch, dataset=dataset, node_id=node_id, names=after)
    # An account group is branch-agnostic, so the delete applies to the two branches.
    group = await NodeManager.get_one(db=db, branch=branch, id=dataset.ids["network-emea"], raise_on_error=True)
    await group.delete(db=db)

    assert await holder.read(db=db, branch=branch, node_id=node_id) == dataset.owners(after)
    diff = await update_diff(db=db, default_branch=default_branch, branch=branch, diff_repository=diff_repository)
    owners = holder.diff_property(diff=diff, node_id=node_id)
    assert (owners.previous_value, owners.new_value, owners.conflict) == (
        holder.diff_value(dataset=dataset, names=START),
        holder.diff_value(dataset=dataset, names=after),
        None,
    )

    await merge(db=db, branch=branch)

    for read_branch in (default_branch, branch):
        assert await holder.read(db=db, branch=read_branch, node_id=node_id) == dataset.owners(after)
    await verify_graph(db=db)
