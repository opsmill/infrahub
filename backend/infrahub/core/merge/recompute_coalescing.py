"""Coalesce a merge or rebase change set into one deduplicated recompute."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from infrahub.display_labels.scoping import derive_display_label_targets
from infrahub.hfid.scoping import derive_hfid_targets
from infrahub.workflows.catalogue import (
    COMPUTED_ATTRIBUTE_PROCESS_JINJA2,
    DISPLAY_LABELS_PROCESS_JINJA2,
    HFID_PROCESS,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.events.models import EventContext
    from infrahub.services.adapters.workflow import InfrahubWorkflow
    from infrahub.workflows.models import WorkflowDefinition

COMPUTED_ATTRIBUTE = "computed_attribute"
DISPLAY_LABEL = "display_label"
HFID = "hfid"

CREATED = "created"
UPDATED = "updated"
DELETED = "deleted"

_SELF_FILTER = "ids"


@dataclass(frozen=True)
class MergeChange:
    """One changed node from the merge or rebase diff changelog."""

    node_id: str
    kind: str
    action: str
    changed_fields: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ChangeSignature:
    """The dedup key for derivation: changes sharing it derive the same targets."""

    kind: str
    action: str
    changed_fields: frozenset[str]


@dataclass(frozen=True)
class ReaderLookup:
    """How to locate the nodes to recompute for one source kind over one set of changes.

    ``source_kind`` is the changed node kind, which the per-family recompute flow uses to
    resolve the relationship and the reader query; it equals the target kind for a self or
    creation lookup. ``filter_key`` is ``"ids"`` when the changed nodes are themselves the
    targets, or ``"<relationship>__ids"`` when the targets read the changed nodes across a
    relationship. ``source_node_ids`` are the changed node ids the lookup runs over.
    """

    source_kind: str
    filter_key: str
    source_node_ids: frozenset[str]


@dataclass(frozen=True)
class AffectedTarget:
    """A derived value to recompute, deduplicated across all changes.

    ``attribute_name`` is set for a computed attribute and ``None`` for a display
    label or human-friendly id. ``reader_lookups`` is the union of every way this
    target is reached by the change set, so its readers are resolved by one query
    over the union rather than one per changed node. ``precise`` is ``False`` when a
    bounded over-approximation was used instead of an exact derivation.
    """

    family: str
    target_kind: str
    attribute_name: str | None
    reads_across_relationship: bool
    reader_lookups: frozenset[ReaderLookup]
    precise: bool = True


@dataclass(frozen=True)
class CoalescedRecompute:
    """The deduplicated recompute one merge or rebase submits, on one branch.

    ``branch`` is the destination branch for a merge and the user branch for a
    rebase. ``targets`` is the union over all changes, deduplicated so a derived
    value is recomputed at most once.
    """

    branch: str
    targets: frozenset[AffectedTarget]

    @property
    def fallback_used(self) -> bool:
        return any(not target.precise for target in self.targets)


@dataclass
class _ResolvedTarget:
    family: str
    target_kind: str
    attribute_name: str | None
    filter_key: str
    reads_across_relationship: bool
    precise: bool


@dataclass
class _TargetAccumulator:
    family: str
    target_kind: str
    attribute_name: str | None
    reads_across_relationship: bool = False
    precise: bool = True
    ids_by_lookup: dict[tuple[str, str], set[str]] = field(default_factory=dict)

    def add(self, *, resolved: _ResolvedTarget, source_kind: str, source_node_ids: frozenset[str]) -> None:
        self.ids_by_lookup.setdefault((source_kind, resolved.filter_key), set()).update(source_node_ids)
        if resolved.reads_across_relationship:
            self.reads_across_relationship = True
        if not resolved.precise:
            self.precise = False

    def freeze(self) -> AffectedTarget:
        return AffectedTarget(
            family=self.family,
            target_kind=self.target_kind,
            attribute_name=self.attribute_name,
            reads_across_relationship=self.reads_across_relationship,
            reader_lookups=frozenset(
                ReaderLookup(source_kind=source_kind, filter_key=filter_key, source_node_ids=frozenset(ids))
                for (source_kind, filter_key), ids in self.ids_by_lookup.items()
            ),
            precise=self.precise,
        )


def build_coalesced_recompute(
    *,
    changes: Iterable[MergeChange],
    schema_branch: SchemaBranch,
    branch: str,
) -> CoalescedRecompute:
    """Build the deduplicated recompute for a merge or rebase change set.

    Groups the changes by signature so derivation runs once per distinct change
    shape, runs the three family derivers, and merges the results so each derived
    target is recomputed once with its reader lookups unioned.

    Targets come only from the changes in the set. A branch-originated merge carries every level the
    branch already cascaded, so a transitive chain is covered in one pass; a level absent from the set
    (a destination-only reader, or a rebase whose source branch had no readers) is reached instead by
    the live recompute its predecessor's write triggers.
    """
    ids_by_signature: dict[ChangeSignature, set[str]] = {}
    for change in changes:
        signature = ChangeSignature(kind=change.kind, action=change.action, changed_fields=change.changed_fields)
        ids_by_signature.setdefault(signature, set()).add(change.node_id)

    accumulators: dict[tuple[str, str, str | None], _TargetAccumulator] = {}
    for signature, node_ids in ids_by_signature.items():
        source_node_ids = frozenset(node_ids)
        for resolved in _resolve_targets(signature=signature, schema_branch=schema_branch):
            key = (resolved.family, resolved.target_kind, resolved.attribute_name)
            accumulator = accumulators.get(key)
            if accumulator is None:
                accumulator = _TargetAccumulator(
                    family=resolved.family,
                    target_kind=resolved.target_kind,
                    attribute_name=resolved.attribute_name,
                )
                accumulators[key] = accumulator
            accumulator.add(resolved=resolved, source_kind=signature.kind, source_node_ids=source_node_ids)

    return CoalescedRecompute(
        branch=branch,
        targets=frozenset(accumulator.freeze() for accumulator in accumulators.values()),
    )


def _resolve_targets(*, signature: ChangeSignature, schema_branch: SchemaBranch) -> Iterator[_ResolvedTarget]:
    if signature.action == CREATED:
        include_self, include_cross = True, False
        fields: frozenset[str] | None = None
        precise = True
    elif signature.action == UPDATED:
        include_self, include_cross = False, True
        # An update with no recorded fields cannot be scoped, so fall back to every
        # field rather than risk missing a reader (over-recompute is safe).
        fields = signature.changed_fields or None
        precise = bool(signature.changed_fields)
    elif signature.action == DELETED:
        include_self, include_cross = False, True
        fields = None
        precise = True
    else:
        raise ValueError(f"Unknown change action: {signature.action!r}")

    yield from _resolve_computed_targets(
        schema_branch=schema_branch,
        kind=signature.kind,
        fields=fields,
        include_self=include_self,
        include_cross=include_cross,
        precise=precise,
    )

    for display_target in derive_display_label_targets(
        display_labels=schema_branch.display_labels,
        kind=signature.kind,
        changed_fields=fields,
        include_self=include_self,
        include_cross=include_cross,
    ):
        yield _ResolvedTarget(
            family=DISPLAY_LABEL,
            target_kind=display_target.target_kind,
            attribute_name=None,
            filter_key=display_target.filter_key,
            reads_across_relationship=display_target.reads_across_relationship,
            precise=precise,
        )

    for hfid_target in derive_hfid_targets(
        hfids=schema_branch.hfids,
        kind=signature.kind,
        changed_fields=fields,
        include_self=include_self,
        include_cross=include_cross,
    ):
        yield _ResolvedTarget(
            family=HFID,
            target_kind=hfid_target.target_kind,
            attribute_name=None,
            filter_key=hfid_target.filter_key,
            reads_across_relationship=hfid_target.reads_across_relationship,
            precise=precise,
        )


def _resolve_computed_targets(
    *,
    schema_branch: SchemaBranch,
    kind: str,
    fields: frozenset[str] | None,
    include_self: bool,
    include_cross: bool,
    precise: bool,
) -> Iterator[_ResolvedTarget]:
    updates = sorted(fields) if fields is not None else None
    for resolved in schema_branch.computed_attributes.get_impacted_jinja2_targets(kind, updates):
        target_kind = resolved.target.kind
        attribute_name = resolved.target.attribute.name
        for filter_key in resolved.node_filters:
            is_self = filter_key == _SELF_FILTER
            if is_self and not (include_self and target_kind == kind):
                continue
            if not is_self and not include_cross:
                continue
            yield _ResolvedTarget(
                family=COMPUTED_ATTRIBUTE,
                target_kind=target_kind,
                attribute_name=attribute_name,
                filter_key=filter_key,
                reads_across_relationship=not is_self,
                precise=precise,
            )


@dataclass(frozen=True)
class CoalescedSubmission:
    """One reuse of an existing per-family process flow over the union of changed nodes.

    The process flow resolves its reader query from ``source_kind`` and ``target_kind`` and
    runs it once over ``node_ids``, so the recompute scales with the affected derived values,
    not the changed-node count times the matching automations.
    """

    family: str
    source_kind: str
    target_kind: str
    attribute_name: str | None
    filter_key: str
    branch: str
    node_ids: tuple[str, ...]


def plan_coalesced_submissions(coalesced: CoalescedRecompute) -> list[CoalescedSubmission]:
    """Turn a coalesced recompute into the deduplicated, ordered set of process-flow submissions.

    One submission per derived target and source kind, each carrying the union of changed node
    ids. The order is deterministic so the same change set always submits the same work.
    """
    submissions = [
        CoalescedSubmission(
            family=target.family,
            source_kind=lookup.source_kind,
            target_kind=target.target_kind,
            attribute_name=target.attribute_name,
            filter_key=lookup.filter_key,
            branch=coalesced.branch,
            node_ids=tuple(sorted(lookup.source_node_ids)),
        )
        for target in coalesced.targets
        for lookup in target.reader_lookups
    ]
    return sorted(
        submissions,
        key=lambda submission: (
            submission.family,
            submission.target_kind,
            submission.attribute_name or "",
            submission.source_kind,
            submission.filter_key,
        ),
    )


def _submission_workflow(
    *, submission: CoalescedSubmission, context: EventContext
) -> tuple[WorkflowDefinition, dict[str, Any]]:
    parameters: dict[str, Any] = {
        "branch_name": submission.branch,
        "node_kind": submission.source_kind,
        "object_ids": list(submission.node_ids),
        "context": context,
    }
    if submission.family == COMPUTED_ATTRIBUTE:
        parameters["computed_attribute_name"] = submission.attribute_name
        parameters["computed_attribute_kind"] = submission.target_kind
        return COMPUTED_ATTRIBUTE_PROCESS_JINJA2, parameters
    if submission.family == DISPLAY_LABEL:
        parameters["target_kind"] = submission.target_kind
        return DISPLAY_LABELS_PROCESS_JINJA2, parameters
    if submission.family == HFID:
        parameters["target_kind"] = submission.target_kind
        return HFID_PROCESS, parameters
    raise ValueError(f"Unknown recompute family: {submission.family!r}")


async def submit_coalesced_recompute(
    *,
    coalesced: CoalescedRecompute,
    workflow: InfrahubWorkflow,
    context: EventContext,
) -> list[CoalescedSubmission]:
    """Submit the coalesced recompute by reusing the existing per-family process flows.

    Each submission runs one process flow over the union of changed nodes, so the merge and
    rebase path no longer dispatches one flow per changed node. Returns the submissions made.
    """
    submissions = plan_coalesced_submissions(coalesced)
    for submission in submissions:
        workflow_definition, parameters = _submission_workflow(submission=submission, context=context)
        await workflow.submit_workflow(workflow=workflow_definition, context=context, parameters=parameters)
    return submissions
