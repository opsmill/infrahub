from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime  # noqa: TC003  # Pydantic resolves the field annotations at runtime
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003  # Pydantic resolves the field annotations at runtime

from pydantic import BaseModel, ConfigDict, ValidationError

from infrahub.core.constants import BranchSupportType, ValidatorConclusion
from infrahub.core.regeneration.predicates import definition_changed, query_changed
from infrahub.proposed_change.branch_changes import BranchDiffWindow

if TYPE_CHECKING:
    from collections.abc import Awaitable, Collection

    from infrahub_sdk.diff import NodeDiff

    from infrahub.core.regeneration.models import RegenerationDefinition
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.message_bus.types import ProposedChangeRepository
    from infrahub.proposed_change.branch_changes import BranchChanges
    from infrahub.services.adapters.cache import InfrahubCache

ARTIFACT_VALIDATION_RECORD_TTL_SECONDS = 30 * 24 * 60 * 60
"""How long a proposed change can stay idle before its next artifact validation covers the whole diff again."""

GROUP_MEMBERS_RELATIONSHIP = "members"


class ArtifactValidationRecord(BaseModel):
    """The state of a branch that one artifact validation of a definition read.

    ``completed`` is true only once every check of that validation ran, and ``failed_target_ids`` holds
    the targets whose check did not succeed. A validation in progress holds the record with its own
    pipeline id, so a validation that started later cannot be mistaken for the one that completed.
    """

    model_config = ConfigDict(frozen=True)

    pipeline_id: UUID
    completed: bool
    diff_from_time: datetime
    diff_to_time: datetime
    source_commit: str
    destination_commit: str
    failed_target_ids: frozenset[str] = frozenset()


class ArtifactValidationCompletion(BaseModel):
    """The outcome of a validation that ran every check, stored as its completion mark."""

    model_config = ConfigDict(frozen=True)

    failed_target_ids: frozenset[str]


class ArtifactValidationRecords:
    """The artifact validation records of one proposed change, kept in the cache.

    A missing record is always safe: the next validation then covers the whole diff of the branch. A
    record is completed only when a readable completion mark exists for its own pipeline id, so a
    validation that completes after another one started cannot mark the newer record as completed.
    """

    def __init__(self, cache: InfrahubCache, proposed_change_id: str) -> None:
        self._cache = cache
        self._proposed_change_id = proposed_change_id

    async def get(self, definition_ids: list[str]) -> dict[str, ArtifactValidationRecord]:
        """Return the stored record of each definition that has one."""
        if not definition_ids:
            return {}
        payloads = await self._cache.get_values(keys=[self._key(definition_id) for definition_id in definition_ids])
        stored = {
            definition_id: ArtifactValidationRecord.model_validate_json(payload)
            for definition_id, payload in zip(definition_ids, payloads, strict=True)
            if payload
        }
        if not stored:
            return {}
        marks = await self._cache.get_values(
            keys=[
                self._completion_key(definition_id=definition_id, pipeline_id=record.pipeline_id)
                for definition_id, record in stored.items()
            ]
        )
        records: dict[str, ArtifactValidationRecord] = {}
        for (definition_id, record), mark in zip(stored.items(), marks, strict=True):
            completion = _read_completion(mark=mark)
            records[definition_id] = record.model_copy(
                update={
                    "completed": completion is not None,
                    "failed_target_ids": completion.failed_target_ids if completion is not None else frozenset(),
                }
            )
        return records

    async def start(self, definition_id: str, record: ArtifactValidationRecord) -> None:
        """Replace the stored record with the one of a validation that starts."""
        await self._set(
            definition_id=definition_id,
            record=record.model_copy(update={"completed": False, "failed_target_ids": frozenset()}),
        )

    async def complete(
        self, definition_id: str, record: ArtifactValidationRecord, failed_target_ids: Collection[str]
    ) -> None:
        """Mark the validation of the record's pipeline id as completed, with the targets whose check failed."""
        await self._cache.set(
            key=self._completion_key(definition_id=definition_id, pipeline_id=record.pipeline_id),
            value=ArtifactValidationCompletion(failed_target_ids=frozenset(failed_target_ids)).model_dump_json(),
            expires=ARTIFACT_VALIDATION_RECORD_TTL_SECONDS,
        )

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

    def _completion_key(self, definition_id: str, pipeline_id: UUID) -> str:
        return f"{self._key(definition_id=definition_id)}:{pipeline_id}:completed"


def _read_completion(mark: str | None) -> ArtifactValidationCompletion | None:
    if not mark:
        return None
    try:
        return ArtifactValidationCompletion.model_validate_json(mark)
    except ValidationError:
        return None


def record_matches_validator(*, record: ArtifactValidationRecord, conclusion: str | None) -> bool:
    """Whether the validator of a definition shows the outcome its completed record holds.

    A validator can be changed outside the validation the record describes; the record is then not
    relied on.
    """
    if record.failed_target_ids:
        return conclusion == ValidatorConclusion.FAILURE.value
    return conclusion == ValidatorConclusion.SUCCESS.value


def changes_validated_until(
    *,
    record: ArtifactValidationRecord | None,
    window: BranchDiffWindow | None,
    repository: ProposedChangeRepository | None,
) -> datetime | None:
    """Return the time up to which a completed validation already covered the changes of the branch.

    None means that no completed validation can be relied on, so every change of the diff counts. That
    is the case when the branch was rebased since (the diff starts at another time), when the
    repository of the definition moved on either branch (the files of the transformation may differ),
    or when the diff read now is older than the one that was validated.
    """
    if record is None or not record.completed or window is None or repository is None:
        return None
    if record.diff_from_time != window.from_time or record.diff_to_time > window.to_time:
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
    branch a completed validation already covered and which of its targets failed. ``window`` is the
    time window of the branch diff this run read; it is None when that diff cannot be relied on, and
    the validation then covers the whole diff and leaves no record.
    """

    def __init__(
        self,
        *,
        records: ArtifactValidationRecords,
        definition_id: str,
        pipeline_id: UUID,
        window: BranchDiffWindow | None,
        repository: ProposedChangeRepository,
    ) -> None:
        self._records = records
        self._definition_id = definition_id
        self._window = window
        self._repository = repository
        self._record = (
            ArtifactValidationRecord(
                pipeline_id=pipeline_id,
                completed=False,
                diff_from_time=window.from_time,
                diff_to_time=window.to_time,
                source_commit=repository.source_commit,
                destination_commit=repository.destination_commit,
            )
            if window is not None
            else None
        )
        self._validated_until: datetime | None = None
        self._targets_to_retry: frozenset[str] = frozenset()

    async def start(self, *, previous_conclusion: str | None) -> None:
        """Replace the stored record with the one of this validation.

        ``previous_conclusion`` is the conclusion of the validator of a completed earlier validation, or
        None when the validator is missing or not completed. The record of that validation is relied on
        only when the validator shows the outcome the record holds.
        """
        self._validated_until = None
        self._targets_to_retry = frozenset()
        if previous_conclusion is not None:
            previous_record = (await self._records.get(definition_ids=[self._definition_id])).get(self._definition_id)
            if previous_record is not None and record_matches_validator(
                record=previous_record, conclusion=previous_conclusion
            ):
                self._validated_until = changes_validated_until(
                    record=previous_record, window=self._window, repository=self._repository
                )
                if self._validated_until is not None:
                    self._targets_to_retry = previous_record.failed_target_ids
        if self._record is None:
            await self._records.discard(definition_id=self._definition_id)
        else:
            await self._records.start(definition_id=self._definition_id, record=self._record)

    @property
    def unvalidated_window(self) -> BranchDiffWindow | None:
        """The time window of the changes no completed validation covered, or None when it is the whole diff."""
        if self._window is None or self._validated_until is None:
            return None
        return BranchDiffWindow(from_time=self._validated_until, to_time=self._window.to_time)

    @property
    def targets_to_retry(self) -> frozenset[str]:
        """The targets whose check failed in the completed validation this run relies on."""
        return self._targets_to_retry

    def changes_to_validate(
        self,
        *,
        diff_summary: list[NodeDiff],
        unvalidated_changes: BranchChanges | None,
        target_group_id: str | None,
        members_with_artifact: Collection[str],
    ) -> ChangesToValidate:
        """Return the changes that no completed validation covered.

        ``unvalidated_changes`` holds the changes made in ``unvalidated_window``. The whole diff summary
        is returned when there are none to rely on, and when a member that has an artifact joined the
        target group since that validation: its artifact was not checked while the member was out of
        the group. It is also returned when ``target_group_id`` is None, which stands for a group whose
        member changes the diff does not hold.
        """
        if self._validated_until is None or unvalidated_changes is None or target_group_id is None:
            return ChangesToValidate(diff_summary=diff_summary, validated_until=None)
        changed_members = unvalidated_changes.peers_changed(
            node_id=target_group_id, relationship_name=GROUP_MEMBERS_RELATIONSHIP
        )
        if any(member_id in members_with_artifact for member_id in changed_members):
            return ChangesToValidate(diff_summary=diff_summary, validated_until=None)
        return ChangesToValidate(diff_summary=unvalidated_changes.diff_summary, validated_until=self._validated_until)

    async def complete(self, *, failed_target_ids: Collection[str]) -> None:
        """Mark the record as completed, to call once every check of this validation ran."""
        if self._record is not None:
            await self._records.complete(
                definition_id=self._definition_id, record=self._record, failed_target_ids=failed_target_ids
            )


class TargetCheckOutcomes:
    """The targets whose artifact check did not succeed in one validation.

    A check that raises counts as failed, and the exception is raised again.
    """

    def __init__(self) -> None:
        self._failed_target_ids: set[str] = set()

    async def track(self, *, target_id: str, check: Awaitable[ValidatorConclusion]) -> ValidatorConclusion:
        try:
            conclusion = await check
        except Exception:
            self._failed_target_ids.add(target_id)
            raise
        if conclusion != ValidatorConclusion.SUCCESS:
            self._failed_target_ids.add(target_id)
        return conclusion

    @property
    def failed_target_ids(self) -> frozenset[str]:
        return frozenset(self._failed_target_ids)


@dataclass(frozen=True, kw_only=True, slots=True)
class RecentChanges:
    """The changes made on a branch since a completed validation."""

    changes: BranchChanges
    modified_kinds: list[str]
    """The kinds of the changed nodes, plus the node kind behind each changed profile."""


def changes_reach_definition(
    *,
    definition: RegenerationDefinition,
    target_group_id: str,
    read_kinds: Collection[str],
    recent_changes: RecentChanges,
) -> bool:
    """Whether the changes made since a completed validation of an artifact definition call for a new one.

    They do when the query or the definition changed, when a kind the query reads changed, or when
    the target group gained or lost a member.
    """
    diff_summary = recent_changes.changes.diff_summary
    if query_changed(definition=definition, diff_summary=diff_summary).matched:
        return True
    if definition_changed(definition=definition, diff_summary=diff_summary).matched:
        return True
    if any(kind in read_kinds for kind in recent_changes.modified_kinds):
        return True
    return bool(
        recent_changes.changes.peers_changed(node_id=target_group_id, relationship_name=GROUP_MEMBERS_RELATIONSHIP)
    )


def diff_tracks_members(*, group_kind: str, schema_branch: SchemaBranch) -> bool:
    """Whether a branch diff holds the member changes of a group of this kind.

    It holds none for a group that is local to its branch or shared by every branch.
    """
    members = schema_branch.get(name=group_kind, duplicate=False).get_relationship(name=GROUP_MEMBERS_RELATIONSHIP)
    return members.branch is BranchSupportType.AWARE
