"""Coalesce a merge or rebase change set into one deduplicated recompute."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, assert_never

from infrahub.display_labels.scoping import derive_display_label_targets
from infrahub.events.limits import get_submission_chunk_size
from infrahub.hfid.scoping import derive_hfid_targets
from infrahub.log import get_logger
from infrahub.utilities.chunks import chunked
from infrahub.workflows.catalogue import (
    COMPUTED_ATTRIBUTE_PROCESS_JINJA2,
    COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM,
    DISPLAY_LABELS_PROCESS_JINJA2,
    HFID_PROCESS,
    TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES,
)

log = get_logger()

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

    from infrahub.core.merge.python_target_resolution import PythonTargetResolver
    from infrahub.core.recompute.bulk_write import WrittenNode
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.timestamp import Timestamp
    from infrahub.events.models import EventContext
    from infrahub.services.adapters.workflow import InfrahubWorkflow
    from infrahub.workflows.models import WorkflowDefinition

RecomputeFamily = Literal["computed_attribute", "display_label", "hfid", "python_attribute"]

COMPUTED_ATTRIBUTE: RecomputeFamily = "computed_attribute"
DISPLAY_LABEL: RecomputeFamily = "display_label"
HFID: RecomputeFamily = "hfid"
PYTHON_ATTRIBUTE: RecomputeFamily = "python_attribute"

CREATED = "created"
UPDATED = "updated"
DELETED = "deleted"

_SELF_FILTER = "ids"

# Floor for the schema-derived chain bound; the bound only guards a cyclic schema.
RECOMPUTE_CHAIN_DEPTH_FLOOR = 10


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

    family: RecomputeFamily
    target_kind: str
    attribute_name: str | None
    reads_across_relationship: bool
    reader_lookups: frozenset[ReaderLookup]
    precise: bool = True
    whole_kind: bool = False
    """Recompute every node of ``target_kind`` instead of the ids in ``reader_lookups``.

    A widened target carries no node ids, and an empty id set chunks into no submissions at
    all, so the widening has to be stated rather than left implicit or it silently becomes a
    skip. Set together with ``precise=False``.
    """


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
    family: RecomputeFamily
    target_kind: str
    attribute_name: str | None
    reads_across_relationship: bool
    precise: bool
    filter_key: str | None = None
    """How the changed nodes reach this target, or ``None`` when its ids are resolved downstream.

    The schema says which nodes reach a template-derived value; for a Python transform that
    lives in the stored query instead, so the builder names the target and leaves its ids to
    the resolution step.
    """


@dataclass
class _TargetAccumulator:
    family: RecomputeFamily
    target_kind: str
    attribute_name: str | None
    reads_across_relationship: bool = False
    precise: bool = True
    ids_by_lookup: dict[tuple[str, str], set[str]] = field(default_factory=dict)

    def add(self, *, resolved: _ResolvedTarget, source_kind: str, source_node_ids: frozenset[str]) -> None:
        if resolved.filter_key is not None:
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


@dataclass(frozen=True)
class CoalescedSubmission:
    """One reuse of an existing per-family process flow over a chunk of the changed nodes.

    The process flow resolves its reader query from ``source_kind`` and ``target_kind`` and
    runs it once over ``node_ids``, so the recompute scales with the affected derived values,
    not the changed-node count times the matching automations. ``filter_key`` groups the node
    ids for deduplication and orders the submissions deterministically; the flow re-derives its
    own query filter and does not read it.
    """

    family: RecomputeFamily
    source_kind: str
    target_kind: str
    attribute_name: str | None
    filter_key: str
    branch: str
    node_ids: tuple[str, ...]
    whole_kind: bool = False


class CoalescedRecomputeBuilder:
    """Derive the deduplicated recompute for a merge or rebase change set from one schema branch."""

    def __init__(self, schema_branch: SchemaBranch) -> None:
        self.schema_branch = schema_branch

    def build(self, *, changes: Iterable[MergeChange], branch: str) -> CoalescedRecompute:
        """Derive the deduplicated set of derived values to recompute for a merge or rebase.

        Changes are grouped by their (kind, action, changed fields) signature so the derivation runs
        once per distinct shape, then the three family derivers (computed attribute, display label,
        human-friendly id) produce the affected targets. Targets are deduplicated across the whole
        change set, and each target's reader lookups are unioned so its readers are found by one
        query rather than one per changed node.

        Only the nodes in this change set drive the derivation. A derived value that reads a changed
        node but is not itself in the change set (for example a reader that exists only on the
        destination branch) is not recomputed here; it is reached by the ordinary live recompute
        that fires when this pass writes the value that reader depends on.
        """
        ids_by_signature: dict[ChangeSignature, set[str]] = {}
        for change in changes:
            signature = ChangeSignature(kind=change.kind, action=change.action, changed_fields=change.changed_fields)
            ids_by_signature.setdefault(signature, set()).add(change.node_id)

        accumulators: dict[tuple[str, str, str | None], _TargetAccumulator] = {}
        for signature, node_ids in ids_by_signature.items():
            source_node_ids = frozenset(node_ids)
            for resolved in self._resolve_targets(signature=signature):
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

    def _resolve_targets(self, *, signature: ChangeSignature) -> Iterator[_ResolvedTarget]:
        if signature.action == CREATED:
            yield from self._derive_family_targets(
                kind=signature.kind, fields=None, include_self=True, include_cross=False, precise=True
            )
            return
        if signature.action == DELETED:
            yield from self._derive_family_targets(
                kind=signature.kind, fields=None, include_self=False, include_cross=True, precise=True
            )
            return
        if signature.action == UPDATED:
            if not signature.changed_fields:
                # No fields to scope on: recompute self and cross, since the unknown change may be a
                # relationship the node reads and under-recompute is not acceptable.
                yield from self._derive_family_targets(
                    kind=signature.kind, fields=None, include_self=True, include_cross=True, precise=False
                )
                return
            # The node refreshed its own values inline on the save; only cross-node readers remain.
            yield from self._derive_family_targets(
                kind=signature.kind,
                fields=signature.changed_fields,
                include_self=False,
                include_cross=True,
                precise=True,
                self_refreshed_inline=True,
            )
            # A relationship change that doesn't save the reader (e.g. a peer deleted on another branch)
            # skips the reader's inline recompute, so refresh its own values here.
            relationship_fields = self._changed_relationship_fields(
                kind=signature.kind, changed_fields=signature.changed_fields
            )
            if relationship_fields:
                yield from self._derive_family_targets(
                    kind=signature.kind,
                    fields=relationship_fields,
                    include_self=True,
                    include_cross=False,
                    precise=True,
                )
            return
        raise ValueError(f"Unknown change action: {signature.action!r}")

    def _changed_relationship_fields(self, *, kind: str, changed_fields: frozenset[str]) -> frozenset[str] | None:
        """Return the changed fields that name a relationship on ``kind`` (None if none).

        Any node-like kind (profiles and templates included) carries relationships, and a kind absent
        from the branch yields None instead of raising.
        """
        if not self.schema_branch.has(name=kind):
            return None
        node_schema = self.schema_branch.get(name=kind, duplicate=False)
        matched = changed_fields & {relationship.name for relationship in node_schema.relationships}
        return frozenset(matched) or None

    def _derive_family_targets(
        self,
        *,
        kind: str,
        fields: frozenset[str] | None,
        include_self: bool,
        include_cross: bool,
        precise: bool,
        self_refreshed_inline: bool = False,
    ) -> Iterator[_ResolvedTarget]:
        # A Python transform runs from an automation instead of inline on the node's save, so the
        # owner axis stays on where the other three families correctly drop it.
        yield from self._resolve_python_targets(
            kind=kind,
            include_self=include_self or self_refreshed_inline,
            include_cross=include_cross,
            precise=precise,
        )

        yield from self._resolve_computed_targets(
            kind=kind,
            fields=fields,
            include_self=include_self,
            include_cross=include_cross,
            precise=precise,
        )

        for display_target in derive_display_label_targets(
            display_labels=self.schema_branch.display_labels,
            kind=kind,
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
            hfids=self.schema_branch.hfids,
            kind=kind,
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
        self,
        *,
        kind: str,
        fields: frozenset[str] | None,
        include_self: bool,
        include_cross: bool,
        precise: bool,
    ) -> Iterator[_ResolvedTarget]:
        updates = sorted(fields) if fields is not None else None
        for resolved in self.schema_branch.computed_attributes.get_impacted_jinja2_targets(kind, updates):
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

    def _resolve_python_targets(
        self, *, kind: str, include_self: bool, include_cross: bool, precise: bool
    ) -> Iterator[_ResolvedTarget]:
        """Every Python computed attribute a change to ``kind`` may affect, before any narrowing.

        Which kinds a transform reads lives in its stored GraphQL query rather than in the
        schema, so nothing here can rule an attribute out on the reader axis; every registered
        attribute is a candidate and the resolution step drops the ones that read nothing the
        change touched. The owner axis, where the changed node holds the attribute itself, is
        the one case the schema does decide.
        """
        for target_kind, attributes in self.schema_branch.computed_attributes.get_python_attributes_per_node().items():
            if not include_cross and not (include_self and target_kind == kind):
                continue
            for attribute in attributes:
                yield _ResolvedTarget(
                    family=PYTHON_ATTRIBUTE,
                    target_kind=target_kind,
                    attribute_name=attribute.name,
                    reads_across_relationship=target_kind != kind,
                    precise=precise,
                )


class CoalescedRecomputeSubmitter:
    """Submit a coalesced recompute by reusing the existing per-family process flows."""

    def __init__(self, workflow: InfrahubWorkflow) -> None:
        self.workflow = workflow

    @staticmethod
    def plan(coalesced: CoalescedRecompute) -> list[CoalescedSubmission]:
        """Turn a coalesced recompute into the deduplicated, ordered set of process-flow submissions.

        One submission per derived target and source kind, each carrying the changed node ids. A
        target whose union exceeds the submission chunk size is split into several submissions so no
        flow-run parameter grows past the size Prefect accepts. The order is deterministic so the
        same change set always submits the same work.
        """
        chunk_size = get_submission_chunk_size()
        submissions = [
            CoalescedSubmission(
                family=target.family,
                source_kind=lookup.source_kind,
                target_kind=target.target_kind,
                attribute_name=target.attribute_name,
                filter_key=lookup.filter_key,
                branch=coalesced.branch,
                node_ids=chunk,
            )
            for target in coalesced.targets
            if not target.whole_kind
            for lookup in target.reader_lookups
            for chunk in chunked(tuple(sorted(lookup.source_node_ids)), chunk_size)
        ]
        # A widened target carries no ids to chunk over, so it needs its own submission or the
        # chunking above drops it entirely and the fallback becomes a skip.
        submissions += [
            CoalescedSubmission(
                family=target.family,
                source_kind=target.target_kind,
                target_kind=target.target_kind,
                attribute_name=target.attribute_name,
                filter_key=_SELF_FILTER,
                branch=coalesced.branch,
                node_ids=(),
                whole_kind=True,
            )
            for target in coalesced.targets
            if target.whole_kind
        ]
        for target in coalesced.targets:
            if target.family == PYTHON_ATTRIBUTE and not target.whole_kind and not target.reader_lookups:
                # The builder names Python targets and the resolution step gives them their ids.
                # Reaching here without either means the resolution step was skipped, which turns
                # the whole family into a silent no-op.
                log.error(
                    "Coalesced recompute reached submission with an unresolved Python target %s.%s on branch %s",
                    target.target_kind,
                    target.attribute_name,
                    coalesced.branch,
                )
        return sorted(
            submissions,
            key=lambda submission: (
                submission.family,
                submission.target_kind,
                submission.attribute_name or "",
                submission.source_kind,
                submission.filter_key,
                submission.node_ids,
            ),
        )

    @staticmethod
    def _submission_workflow(
        *, submission: CoalescedSubmission, context: EventContext, recompute_depth: int = 0
    ) -> tuple[WorkflowDefinition, dict[str, Any]]:
        parameters: dict[str, Any] = {
            "branch_name": submission.branch,
            "node_kind": submission.source_kind,
            "object_ids": list(submission.node_ids),
            "context": context,
            "recompute_depth": recompute_depth,
        }
        match submission.family:
            case "computed_attribute":
                parameters["computed_attribute_name"] = submission.attribute_name
                parameters["computed_attribute_kind"] = submission.target_kind
                return COMPUTED_ATTRIBUTE_PROCESS_JINJA2, parameters
            case "display_label":
                parameters["target_kind"] = submission.target_kind
                return DISPLAY_LABELS_PROCESS_JINJA2, parameters
            case "hfid":
                parameters["target_kind"] = submission.target_kind
                return HFID_PROCESS, parameters
            case "python_attribute":
                parameters["computed_attribute_name"] = submission.attribute_name
                parameters["computed_attribute_kind"] = submission.target_kind
                parameters["coalesced"] = True
                if submission.whole_kind:
                    # The all-of-kind flow resolves its own node set, so the id list it would
                    # otherwise receive is meaningless here.
                    del parameters["object_ids"]
                    del parameters["node_kind"]
                    return TRIGGER_UPDATE_PYTHON_COMPUTED_ATTRIBUTES, parameters
                return COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM, parameters
            case _:
                assert_never(submission.family)

    async def submit(
        self, *, coalesced: CoalescedRecompute, context: EventContext, recompute_depth: int = 0
    ) -> list[CoalescedSubmission]:
        """Submit the coalesced recompute, one process flow per chunk of changed nodes.

        The merge and rebase path no longer dispatches one flow per changed node. A single
        submission failure is logged and skipped rather than dropping the rest, since a missed
        submission leaves a stale stored value. ``recompute_depth`` is carried to each process flow
        so a chained next level knows how deep it is. Returns the submissions that were dispatched.
        """
        submitted: list[CoalescedSubmission] = []
        for submission in self.plan(coalesced):
            workflow_definition, parameters = self._submission_workflow(
                submission=submission, context=context, recompute_depth=recompute_depth
            )
            try:
                await self.workflow.submit_workflow(
                    workflow=workflow_definition, context=context, parameters=parameters
                )
            except Exception:
                log.exception(
                    "Failed to submit a coalesced recompute for family %s target %s",
                    submission.family,
                    submission.target_kind,
                )
                continue
            submitted.append(submission)
        return submitted


def _drop_schema_covered(*, coalesced: CoalescedRecompute, covered: frozenset[tuple[str, str]]) -> CoalescedRecompute:
    """Remove the Python targets a wider schema-driven refresh already covers.

    Only the Python family: the other three are not refreshed by that pass in the same way, so
    dropping one of them would leave it stale.
    """
    kept = frozenset(
        target
        for target in coalesced.targets
        if target.family != PYTHON_ATTRIBUTE or (target.target_kind, target.attribute_name or "") not in covered
    )
    return CoalescedRecompute(branch=coalesced.branch, targets=kept)


class MergeRecomputeCoordinator:
    """Build the coalesced recompute for a merge or rebase change set, resolve it, and submit it.

    The three steps always run together, and resolution sits between the other two rather than
    beside a single caller: a chained level re-enters here, and one that skipped resolution would
    submit Python targets with no nodes.
    """

    def __init__(
        self,
        builder: CoalescedRecomputeBuilder,
        submitter: CoalescedRecomputeSubmitter,
        resolver: PythonTargetResolver,
    ) -> None:
        self.builder = builder
        self.submitter = submitter
        self.resolver = resolver

    async def run(
        self,
        *,
        changes: Sequence[MergeChange],
        branch: str,
        context: EventContext,
        recompute_depth: int = 0,
        deleted_at: Timestamp | None = None,
        schema_covered_pairs: frozenset[tuple[str, str]] = frozenset(),
    ) -> list[CoalescedSubmission]:
        """``deleted_at`` is the point in time the readers of a deleted node are resolved at.

        A chained level passes none: its change set is the values it just wrote, never a delete.

        ``schema_covered_pairs`` are the ``(kind, attribute)`` pairs a schema-driven refresh on the
        same merge already covers across the whole kind. Dropping them here is the whole point of
        the subtraction: that pass is the wider of the two, so keeping both refreshes the
        overlapping nodes twice.
        """
        coalesced = self.builder.build(changes=changes, branch=branch)
        if schema_covered_pairs:
            coalesced = _drop_schema_covered(coalesced=coalesced, covered=schema_covered_pairs)
        coalesced = await self.resolver.resolve(
            coalesced=coalesced, changes=changes, branch=branch, deleted_at=deleted_at
        )
        return await self.submitter.submit(coalesced=coalesced, context=context, recompute_depth=recompute_depth)


def max_recompute_chain_depth(schema_branch: SchemaBranch) -> int:
    """Chain-depth bound from the schema's derived-value target count (floored).

    A chain can't recompute more targets than the schema has, so this never truncates a real chain
    while still stopping a cyclic schema.
    """
    python_attributes = schema_branch.computed_attributes.get_python_attributes_per_node()
    target_count = (
        len(schema_branch.computed_attributes.get_jinja2_target_map())
        + len(schema_branch.display_labels.get_template_nodes())
        + len(schema_branch.hfids.get_template_nodes())
        + sum(len(attributes) for attributes in python_attributes.values())
    )
    return max(RECOMPUTE_CHAIN_DEPTH_FLOOR, target_count)


class RecomputeChainSubmitter:
    """Dispatch the next recompute level for a set of derived-value writes, as one coalesced pass."""

    def __init__(self, coordinator: MergeRecomputeCoordinator, max_depth: int) -> None:
        self.coordinator = coordinator
        self.max_depth = max_depth

    async def submit(
        self, *, written: list[WrittenNode], branch: str, context: EventContext, depth: int
    ) -> list[CoalescedSubmission]:
        """Build and submit the next coalesced level, or stop the chain.

        The writes are treated like a merge or rebase change set, so a chained level goes through
        the same derivation and resolution as the merge that started it. An empty write set stops
        the chain; the depth bound is the backstop for a cyclic schema.
        """
        if not written:
            return []
        next_depth = depth + 1
        if next_depth > self.max_depth:
            log.warning(
                "Recompute chain exceeded its bound (%s) on branch %s; the derived-value dependency graph "
                "is likely cyclic. Leaving %s node(s) unrecomputed: %s",
                self.max_depth,
                branch,
                len(written),
                sorted({f"{node.kind}:{node.node_id}" for node in written}),
            )
            return []
        changes = [
            MergeChange(node_id=node.node_id, kind=node.kind, action=UPDATED, changed_fields=frozenset(node.fields))
            for node in written
        ]
        return await self.coordinator.run(changes=changes, branch=branch, context=context, recompute_depth=next_depth)
