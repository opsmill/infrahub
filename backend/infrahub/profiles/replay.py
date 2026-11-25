from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from infrahub.core.constants import DiffAction, MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.log import get_logger
from infrahub.utils import log_exception_guard
from infrahub.workflows.catalogue import PROFILE_REFRESH_PROCESS

from .gather import get_profile_trigger_fields

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping, Sequence

    from infrahub.core.changelog.models import NodeChangelog
    from infrahub.core.node import Node
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase
    from infrahub.events.models import EventContext
    from infrahub.services.adapters.workflow import InfrahubWorkflow

log = get_logger()


@dataclass(frozen=True)
class ReplayedProfile:
    """A profile whose refresh fields a merge or a rebase changed."""

    profile_id: str
    profile_kind: str
    attribute_names: list[str] | None
    """The changed attributes a linked node can already hold, or None when every linked node needs the refresh."""


def find_replayed_profiles(
    changelogs: Sequence[tuple[DiffAction, NodeChangelog]], trigger_fields: Mapping[str, Collection[str]]
) -> list[ReplayedProfile]:
    """Return the updated profiles of ``changelogs`` whose change touches the fields that refresh their nodes."""
    profiles: dict[str, ReplayedProfile] = {}
    for action, changelog in changelogs:
        fields = trigger_fields.get(changelog.node_kind)
        if action is not DiffAction.UPDATED or not fields:
            continue
        changed = set(changelog.updated_fields) & set(fields)
        if not changed:
            continue
        # A new priority or relationship can change what a node takes from each of its profiles.
        attribute_names = (
            None if "profile_priority" in changed or not changed.issubset(changelog.attributes) else changed
        )
        if (previous := profiles.get(changelog.node_id)) is not None:
            attribute_names = (
                None
                if previous.attribute_names is None or attribute_names is None
                else attribute_names | set(previous.attribute_names)
            )
        profiles[changelog.node_id] = ReplayedProfile(
            profile_id=changelog.node_id,
            profile_kind=changelog.node_kind,
            attribute_names=sorted(attribute_names) if attribute_names is not None else None,
        )
    return list(profiles.values())


class NodeRefreshFilter(Protocol):
    """Select, from a page of nodes linked to a profile, the nodes that need the profile refresh."""

    async def select(self, node_ids: list[str]) -> list[str]: ...


class RefreshAllNodes:
    """Keep every node, because a change that a node cannot already hold needs the refresh of all the linked nodes."""

    async def select(self, node_ids: list[str]) -> list[str]:
        return node_ids


class ProfileValueFilter:
    """Leave out the nodes that hold, from the profile as their only one, its value of some attributes."""

    def __init__(self, db: InfrahubDatabase, branch_name: str, profile_id: str, values: dict[str, Any]) -> None:
        self.db = db
        self.branch_name = branch_name
        self.profile_id = profile_id
        self.values = values

    async def select(self, node_ids: list[str]) -> list[str]:
        nodes = await NodeManager.get_many(
            db=self.db,
            ids=node_ids,
            branch=self.branch_name,
            fields=dict.fromkeys(self.values),
            include_metadata=MetadataOptions.SOURCE,
        )
        await NodeManager.prefetch_relationships(
            db=self.db, nodes=nodes.values(), names={"profiles"}, branch=self.branch_name
        )
        profile_ids = {
            node_id: [
                rel.peer_id
                for rel in await node.get_relationship(name="profiles").get_relationships(db=self.db)
                if rel.peer_id
            ]
            for node_id, node in nodes.items()
        }
        return [
            node_id
            for node_id in node_ids
            if not _holds(
                node=nodes.get(node_id),
                profile_ids=profile_ids.get(node_id, []),
                profile_id=self.profile_id,
                values=self.values,
            )
        ]


class ProfileValueSelector:
    """Build the filter that leaves out the nodes linked to a profile that hold its value of some attributes."""

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def prepare(self, branch_name: str, profile_id: str, attribute_names: list[str]) -> ProfileValueFilter | None:
        """Return the filter for the current value of each named attribute, or None when the profile does not exist."""
        profile = await NodeManager.get_one(
            db=self.db, id=profile_id, branch=branch_name, fields=dict.fromkeys(attribute_names)
        )
        if profile is None:
            return None
        return ProfileValueFilter(
            db=self.db,
            branch_name=branch_name,
            profile_id=profile_id,
            values={name: profile.get_attribute(name=name).value for name in attribute_names},
        )


def _holds(node: Node | None, profile_ids: list[str], profile_id: str, values: dict[str, Any]) -> bool:
    # Another profile of the node can win an attribute, even when the value and its source did not change.
    if node is None or profile_ids != [profile_id]:
        return False
    # The source tells which profile won, so an equal value from another source still needs the refresh.
    return all(
        node.get_attribute(name=name).source_id == profile_id and node.get_attribute(name=name).value == value
        for name, value in values.items()
    )


class ProfileReplayRefresher:
    """Submit the refresh of the profiles a merge or a rebase changed, for the linked nodes that do not hold the change."""

    def __init__(self, workflow: InfrahubWorkflow) -> None:
        self.workflow = workflow

    async def refresh(
        self,
        branch_name: str,
        schema_branch: SchemaBranch,
        changelogs: Sequence[tuple[DiffAction, NodeChangelog]],
        context: EventContext,
    ) -> None:
        """Submit one profile refresh process for each profile of ``changelogs`` whose refresh fields changed."""
        trigger_fields = {
            profile_name: get_profile_trigger_fields(
                profile_schema=schema_branch.get_profile(name=profile_name, duplicate=False)
            )
            for profile_name in schema_branch.profile_names
        }
        for profile in find_replayed_profiles(changelogs=changelogs, trigger_fields=trigger_fields):
            with log_exception_guard(log, f"Failed to submit the profile refresh of {profile.profile_id}"):
                await self.workflow.submit_workflow(
                    workflow=PROFILE_REFRESH_PROCESS,
                    context=context,
                    parameters={
                        "branch_name": branch_name,
                        "profile_kind": profile.profile_kind,
                        "profile_id": profile.profile_id,
                        "context": context,
                        "attribute_names": profile.attribute_names,
                    },
                )
