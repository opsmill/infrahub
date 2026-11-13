from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime  # noqa: TC003  # Pydantic resolves the field annotations at runtime
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003  # Pydantic resolves the field annotations at runtime

from pydantic import BaseModel, ConfigDict

from infrahub.core.constants import BranchSupportType
from infrahub.core.regeneration.changes_since import changes_since, peers_changed_since
from infrahub.core.regeneration.predicates import definition_changed, query_changed

if TYPE_CHECKING:
    from collections.abc import Collection

    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.regeneration.changes_since import DiffChangeTimes
    from infrahub.core.regeneration.models import RegenerationDefinition
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.message_bus.types import ProposedChangeRepository
    from infrahub.services.adapters.cache import InfrahubCache

ARTIFACT_VALIDATION_RECORD_TTL_SECONDS = 30 * 24 * 60 * 60
"""How long a proposed change can stay idle before its next artifact validation covers the whole diff again."""

GROUP_MEMBERS_RELATIONSHIP = "members"


class ArtifactValidationRecord(BaseModel):
    """The state of a branch that one artifact validation of a definition read.

    ``completed`` is true only once every check of that validation succeeded. A validation in progress
    holds the record with its own pipeline id, so a validation that started later cannot be mistaken
    for the one that completed.
    """

    model_config = ConfigDict(frozen=True)

    pipeline_id: UUID
    completed: bool
    diff_from_time: datetime
    diff_to_time: datetime
    source_commit: str
    destination_commit: str


class ArtifactValidationRecords:
    """The artifact validation records of one proposed change, kept in the cache.

    A missing record is always safe: the next validation then covers the whole diff of the branch.
    """

    def __init__(self, cache: InfrahubCache, proposed_change_id: str) -> None:
        self._cache = cache
        self._proposed_change_id = proposed_change_id

    async def get(self, definition_ids: list[str]) -> dict[str, ArtifactValidationRecord]:
        """Return the stored record of each definition that has one."""
        if not definition_ids:
            return {}
        payloads = await self._cache.get_values(keys=[self._key(definition_id) for definition_id in definition_ids])
        return {
            definition_id: ArtifactValidationRecord.model_validate_json(payload)
            for definition_id, payload in zip(definition_ids, payloads, strict=True)
            if payload
        }

    async def start(self, definition_id: str, record: ArtifactValidationRecord) -> None:
        """Replace the stored record with the one of a validation that starts."""
        await self._set(definition_id=definition_id, record=record.model_copy(update={"completed": False}))

    async def complete(self, definition_id: str, record: ArtifactValidationRecord) -> None:
        """Mark the record as completed, unless another validation started in the meantime."""
        stored = (await self.get(definition_ids=[definition_id])).get(definition_id)
        if stored is None or stored.pipeline_id != record.pipeline_id:
            return
        await self._set(definition_id=definition_id, record=record.model_copy(update={"completed": True}))

    async def discard(self, definition_id: str) -> None:
        await self._cache.delete(key=self._key(definition_id))

    async def _set(self, definition_id: str, record: ArtifactValidationRecord) -> None:
        await self._cache.set(
            key=self._key(definition_id),
            value=record.model_dump_json(),
            expires=ARTIFACT_VALIDATION_RECORD_TTL_SECONDS,
        )

    def _key(self, definition_id: str) -> str:
        return f"proposed_change:{self._proposed_change_id}:artifact_definition:{definition_id}:validation"


def changes_validated_until(
    *,
    record: ArtifactValidationRecord | None,
    change_times: DiffChangeTimes | None,
    repository: ProposedChangeRepository | None,
) -> datetime | None:
    """Return the time up to which a completed validation already covered the changes of the branch.

    None means that no completed validation can be relied on, so every change of the diff counts. That
    is the case when the branch was rebased since (the diff starts at another time), when the
    repository of the definition moved on either branch (the files of the transformation may differ),
    or when the diff read now is older than the one that was validated.
    """
    if record is None or not record.completed or change_times is None or repository is None:
        return None
    if record.diff_from_time != change_times.from_time or record.diff_to_time > change_times.to_time:
        return None
    if record.source_commit != repository.source_commit or record.destination_commit != repository.destination_commit:
        return None
    return record.diff_to_time


@dataclass(frozen=True, kw_only=True, slots=True)
class ChangesToValidate:
    """The changes of a branch diff that one artifact validation selects its targets from."""

    diff_summary: list[NodeDiff]
    validated_until: datetime | None
    """The time up to which a completed validation covered the changes left out, or None when none is left out."""


class ArtifactValidationRun:
    """One validation of an artifact definition in a proposed change.

    It keeps the record of the definition in step with the validation, and tells which changes of the
    branch a completed validation already covered. ``change_times`` is None when the times of the diff
    cannot be relied on, and the validation then covers the whole diff and leaves no record.
    """

    def __init__(
        self,
        *,
        records: ArtifactValidationRecords,
        definition_id: str,
        pipeline_id: UUID,
        change_times: DiffChangeTimes | None,
        repository: ProposedChangeRepository,
    ) -> None:
        self._records = records
        self._definition_id = definition_id
        self._change_times = change_times
        self._repository = repository
        self._record = (
            ArtifactValidationRecord(
                pipeline_id=pipeline_id,
                completed=False,
                diff_from_time=change_times.from_time,
                diff_to_time=change_times.to_time,
                source_commit=repository.source_commit,
                destination_commit=repository.destination_commit,
            )
            if change_times is not None
            else None
        )
        self._validated_until: datetime | None = None

    async def start(self, *, previous_validation_succeeded: bool) -> None:
        """Replace the stored record with the one of this validation.

        The record of an earlier validation is relied on only when ``previous_validation_succeeded``.
        """
        self._validated_until = None
        if previous_validation_succeeded:
            previous_records = await self._records.get(definition_ids=[self._definition_id])
            self._validated_until = changes_validated_until(
                record=previous_records.get(self._definition_id),
                change_times=self._change_times,
                repository=self._repository,
            )
        if self._record is None:
            await self._records.discard(definition_id=self._definition_id)
        else:
            await self._records.start(definition_id=self._definition_id, record=self._record)

    def changes_to_validate(
        self, *, diff_summary: list[NodeDiff], target_group_id: str | None, members_with_artifact: Collection[str]
    ) -> ChangesToValidate:
        """Return the changes of the diff summary that no completed validation covered.

        The whole summary is returned when a member that has an artifact joined the target group since
        that validation: its artifact was not checked while the member was out of the group. It is
        also returned when ``target_group_id`` is None, which stands for a group whose member changes
        the diff does not hold.
        """
        if self._change_times is None or self._validated_until is None or target_group_id is None:
            return ChangesToValidate(diff_summary=diff_summary, validated_until=None)
        changed_members = peers_changed_since(
            change_times=self._change_times,
            node_id=target_group_id,
            relationship_name=GROUP_MEMBERS_RELATIONSHIP,
            since=self._validated_until,
        )
        if any(member_id in members_with_artifact for member_id in changed_members):
            return ChangesToValidate(diff_summary=diff_summary, validated_until=None)
        return ChangesToValidate(
            diff_summary=changes_since(
                diff_summary=diff_summary, change_times=self._change_times, since=self._validated_until
            ),
            validated_until=self._validated_until,
        )

    async def complete(self) -> None:
        """Mark the record as completed, to call once every check of this validation succeeded."""
        if self._record is not None:
            await self._records.complete(definition_id=self._definition_id, record=self._record)


@dataclass(frozen=True, kw_only=True, slots=True)
class RecentChanges:
    """The changes of a branch diff made at or after ``since``."""

    since: datetime
    diff_summary: list[NodeDiff]
    modified_kinds: list[str]
    """The kinds of the changed nodes, plus the node kind behind each changed profile."""


def changes_reach_definition(
    *,
    definition: RegenerationDefinition,
    target_group_id: str | None,
    read_kinds: Collection[str],
    recent_changes: RecentChanges,
    change_times: DiffChangeTimes,
) -> bool:
    """Whether the changes made since a completed validation of an artifact definition call for a new one.

    They do when the query or the definition changed, when a kind the query reads changed, or when
    the target group gained or lost a member. A definition always gets a new validation when
    ``target_group_id`` is None, which stands for a group that is unknown or whose member changes the
    diff does not hold.
    """
    if target_group_id is None:
        return True
    if query_changed(definition=definition, diff_summary=recent_changes.diff_summary).matched:
        return True
    if definition_changed(definition=definition, diff_summary=recent_changes.diff_summary).matched:
        return True
    if any(kind in read_kinds for kind in recent_changes.modified_kinds):
        return True
    return bool(
        peers_changed_since(
            change_times=change_times,
            node_id=target_group_id,
            relationship_name=GROUP_MEMBERS_RELATIONSHIP,
            since=recent_changes.since,
        )
    )


def diff_tracks_members(*, group_kind: str, schema_branch: SchemaBranch) -> bool:
    """Whether a branch diff holds the member changes of a group of this kind.

    It holds none for a group that is local to its branch or shared by every branch.
    """
    members = schema_branch.get(name=group_kind, duplicate=False).get_relationship(name=GROUP_MEMBERS_RELATIONSHIP)
    return members.branch is BranchSupportType.AWARE
