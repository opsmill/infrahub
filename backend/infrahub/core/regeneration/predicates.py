from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.constants import DiffAction
from infrahub.exceptions import NodeNotFoundError
from infrahub.git.closure_builder.canonicalizer import canonicalize_path

from .models import PredicateOutcome, RegenerationReason, RegenerationTrigger

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff

    from infrahub.message_bus.types import ProposedChangeBranchDiff, ProposedChangeRepository

    from .models import RegenerationDefinition


_TRIGGERING_DIFF_ACTIONS = {DiffAction.ADDED.value, DiffAction.UPDATED.value}
_FINGERPRINT_ELEMENT = "fingerprint"


def classify_untrusted_dependency_closure(definition: RegenerationDefinition) -> RegenerationReason | None:
    """Classify why a definition's dependency closure cannot be trusted, or None when it can.

    A closure that was never computed and one computed only partially are distinguished so each path
    can explain itself; both mean a code change outside the known inputs would not move the
    fingerprint, so the definition must be regenerated defensively rather than narrowed.
    """
    if definition.dependencies is None:
        return RegenerationReason.DEPENDENCIES_NULL
    if definition.dependencies_complete is not True:
        return RegenerationReason.DEPENDENCIES_INCOMPLETE
    return None


def is_triggering_action(action: str) -> bool:
    """Return True for diff actions that should trigger artifact regeneration.

    ``get_diff_summary`` serialises a node/element action as the GraphQL enum *name*
    (uppercase, e.g. ``"UPDATED"``/``"ADDED"``), whereas ``DiffAction.*.value`` is
    lowercase. The comparison must therefore be case-insensitive: a literal
    ``action in _TRIGGERING_DIFF_ACTIONS`` silently never matches real diff data.
    """
    return action.lower() in _TRIGGERING_DIFF_ACTIONS


def _find_triggering_entry(diff_summary: list[NodeDiff], node_id: str) -> NodeDiff | None:
    """Return the first triggering diff entry for the given node id, or None when none matches."""
    return next(
        (entry for entry in diff_summary if entry["id"] == node_id and is_triggering_action(entry["action"])),
        None,
    )


def _is_unchanged(action: str) -> bool:
    """Return True for the diff action marking an entry as carrying no change.

    A diff summary serialises an action as the GraphQL enum *name* (uppercase), whereas
    ``DiffAction.*.value`` is lowercase, so the comparison has to be case-insensitive.
    """
    return action.lower() == DiffAction.UNCHANGED.value


def relevant_node_changes(
    diff_summary: list[NodeDiff], query_branch: str, readable_fields_by_kind: dict[str, set[str]]
) -> list[str]:
    """Return ids of nodes whose modified fields intersect the fields a query reads.

    A change is relevant only when at least one modified field is also read by the query, so a
    node whose only change is to a field the query ignores -- or whose kind the query never reads
    -- is excluded. `readable_fields_by_kind` maps each kind the query reads to the set of its
    attribute and relationship names that the query selects.

    Only entries marked unchanged are skipped, at both the node and the element level: a diff can
    carry a node purely as hierarchical context, and can hang an unchanged parent relationship off
    a node that did change, neither of which makes a reader stale. A removed node is deliberately
    kept -- whatever read it is now stale, so dropping it would under-execute.
    """
    relevant_node_ids: list[str] = []
    for node_diff in diff_summary:
        if node_diff["branch"] != query_branch or _is_unchanged(node_diff["action"]):
            continue
        readable_fields = readable_fields_by_kind.get(node_diff["kind"])
        if not readable_fields:
            continue
        updated_fields = {element["name"] for element in node_diff["elements"] if not _is_unchanged(element["action"])}
        if updated_fields & readable_fields:
            relevant_node_ids.append(node_diff["id"])
    return relevant_node_ids


def reads_kind(definition: RegenerationDefinition, kind: str) -> bool:
    """Whether a data change to ``kind`` is relevant because the definition's query reads that kind."""
    return kind in definition.query_models


def query_changed(
    definition: RegenerationDefinition,
    diff_summary: list[NodeDiff],
) -> PredicateOutcome:
    """Match when the definition's GraphQL query node is modified in the diff.

    The SDK inlines every fragment body into the stored query text before persisting,
    so any edit to the primary ``.gql`` file or any transitively referenced fragment
    surfaces as a single ``CoreGraphQLQuery`` node modification. A node-id match is
    therefore sufficient.

    Entries with ``action=unchanged`` are ignored because the diff system enriches
    the tree with parent context nodes that are not themselves modified, and entries
    with ``action=removed`` are ignored because a query deleted on the source branch
    leaves the definition broken and there is nothing to regenerate against.
    """
    if _find_triggering_entry(diff_summary, definition.query_id) is None:
        return PredicateOutcome(matched=False)

    return PredicateOutcome(
        matched=True,
        trigger=RegenerationTrigger(
            code=RegenerationReason.QUERY_CHANGED,
            detail=(
                f"Definition {definition.definition_name} ({definition.definition_id}): "
                f"GraphQL query {definition.query_name} ({definition.query_id}) was modified - "
                f"all {definition.instance_noun} of this definition will regenerate."
            ),
        ),
    )


def definition_changed(
    definition: RegenerationDefinition,
    diff_summary: list[NodeDiff],
) -> PredicateOutcome:
    """Match when the definition node itself is modified in the diff.

    Any attribute change or relationship repoint (e.g. ``targets``, ``query``, and for
    artifact definitions ``transformation``) on the definition surfaces as a modification
    of the definition's own node id, so a single id-based check covers every shape of
    definition-level change uniformly. The reason names the changed attributes or
    relationships read from the matching entry's per-field detail.

    Entries with ``action=unchanged`` are ignored because the diff system enriches
    the tree with parent context nodes that are not themselves modified, and entries
    with ``action=removed`` cannot occur in practice here because the definition list
    is fetched from the source branch's current state.
    """
    matched_entry = _find_triggering_entry(diff_summary, definition.definition_id)
    if matched_entry is None:
        return PredicateOutcome(matched=False)

    changed_field_names = [
        element["name"] for element in matched_entry["elements"] if is_triggering_action(element["action"])
    ]
    detail = "definition node was modified"
    if changed_field_names:
        detail += f" ({', '.join(changed_field_names)})"
    if _FINGERPRINT_ELEMENT in changed_field_names:
        detail += "; the fingerprint moved, so the definition's code inputs changed"
    return PredicateOutcome(
        matched=True,
        trigger=RegenerationTrigger(
            code=RegenerationReason.DEFINITION_CHANGED,
            detail=(
                f"Definition {definition.definition_name} ({definition.definition_id}): {detail} - "
                f"all {definition.instance_noun} of this definition will regenerate."
            ),
        ),
    )


def transform_changed(
    definition: RegenerationDefinition,
    repo_diff: ProposedChangeRepository,
) -> PredicateOutcome:
    """Match when the definition's stored dependency closure intersects this repo's file diff.

    Falls back to "any file changed in the repository" when the closure cannot
    be trusted. On the precise path, both sides are canonicalized before the
    set intersection so the comparison matches git's diff output regardless
    of input separator or leading prefix.

    The two fallback paths are distinguished so each reports the reason it could
    not use the precise closure: a pre-feature node (``dependencies=null``)
    self-heals on its next re-import, while an incomplete closure
    (``dependencies_complete=False``) names the cause as the safety fallback. The
    precise path names the intersecting file(s).
    """
    closure_reason = classify_untrusted_dependency_closure(definition)
    if closure_reason is RegenerationReason.DEPENDENCIES_NULL:
        legacy_detail = (
            f"Definition {definition.definition_name}: {definition.source_noun} was imported before this feature "
            f"deployed (dependencies=null) - falling back to regenerate-on-any-file-change. The next re-import of "
            f"this {definition.source_noun} will populate its dependency closure."
        )
        return PredicateOutcome(
            matched=repo_diff.has_modifications,
            trigger=RegenerationTrigger(code=closure_reason, detail=legacy_detail)
            if repo_diff.has_modifications
            else None,
        )

    if closure_reason is RegenerationReason.DEPENDENCIES_INCOMPLETE:
        incomplete_detail = (
            f"Definition {definition.definition_name}: {definition.source_noun} dependency closure is incomplete "
            f"(dependencies_complete=False) - falling back to regenerate-on-any-file-change."
        )
        return PredicateOutcome(
            matched=repo_diff.has_modifications,
            trigger=RegenerationTrigger(code=closure_reason, detail=incomplete_detail)
            if repo_diff.has_modifications
            else None,
        )

    if not definition.dependencies:
        return PredicateOutcome(matched=False)

    closure = {canonicalize_path(entry) for entry in definition.dependencies}
    changed_files: set[str] = set()
    for raw in (*repo_diff.files_added, *repo_diff.files_changed, *repo_diff.files_removed):
        try:
            changed_files.add(canonicalize_path(raw))
        except ValueError:
            continue

    intersection = closure & changed_files
    if not intersection:
        return PredicateOutcome(matched=False)

    files = ", ".join(sorted(intersection))
    return PredicateOutcome(
        matched=True,
        trigger=RegenerationTrigger(
            code=RegenerationReason.FILE_IN_CLOSURE,
            detail=(
                f"Definition {definition.definition_name}: file {files} changed and is in this "
                f"{definition.source_noun}'s dependency closure - all {definition.instance_noun} will regenerate."
            ),
        ),
    )


def repo_diff_or_none(branch_diff: ProposedChangeBranchDiff, repository_id: str) -> ProposedChangeRepository | None:
    try:
        return branch_diff.get_repository(repository_id)
    except NodeNotFoundError:
        return None
