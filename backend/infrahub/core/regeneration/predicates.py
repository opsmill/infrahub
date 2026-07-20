from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.exceptions import NodeNotFoundError

from infrahub.core.constants import DiffAction
from infrahub.git.closure_builder.canonicalizer import canonicalize_path

from .models import PredicateOutcome

if TYPE_CHECKING:
    from infrahub_sdk.diff import NodeDiff

    from infrahub.message_bus.types import ProposedChangeBranchDiff, ProposedChangeRepository

    from .models import RegenerationDefinition


_TRIGGERING_DIFF_ACTIONS = {DiffAction.ADDED.value, DiffAction.UPDATED.value}


def _is_triggering_action(action: str) -> bool:
    """Return True for diff actions that should trigger artifact regeneration.

    ``get_diff_summary`` serialises a node/element action as the GraphQL enum *name*
    (uppercase, e.g. ``"UPDATED"``/``"ADDED"``), whereas ``DiffAction.*.value`` is
    lowercase. The comparison must therefore be case-insensitive: a literal
    ``action in _TRIGGERING_DIFF_ACTIONS`` silently never matches real diff data.
    """
    return action.lower() in _TRIGGERING_DIFF_ACTIONS


def relevant_node_changes(
    diff_summary: list[NodeDiff], query_branch: str, readable_fields_by_kind: dict[str, set[str]]
) -> list[str]:
    """Return ids of nodes whose modified fields intersect the fields a query reads.

    A change is relevant only when at least one modified field is also read by the query, so a
    node whose only change is to a field the query ignores -- or whose kind the query never reads
    -- is excluded. `readable_fields_by_kind` maps each kind the query reads to the set of its
    attribute and relationship names that the query selects.
    """
    relevant_node_ids: list[str] = []
    for node_diff in diff_summary:
        if node_diff["branch"] != query_branch:
            continue
        readable_fields = readable_fields_by_kind.get(node_diff["kind"])
        if not readable_fields:
            continue
        updated_fields = {element["name"] for element in node_diff["elements"]}
        if updated_fields & readable_fields:
            relevant_node_ids.append(node_diff["id"])
    return relevant_node_ids


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
    matched = any(
        entry["id"] == definition.query_id and _is_triggering_action(entry["action"]) for entry in diff_summary
    )
    if not matched:
        return PredicateOutcome(matched=False)

    return PredicateOutcome(
        matched=True,
        reason=(
            f"Definition {definition.definition_name} ({definition.definition_id}): "
            f"GraphQL query {definition.query_name} ({definition.query_id}) was modified - "
            f"all {definition.instance_noun} of this definition will regenerate."
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
    matched_entry = next(
        (
            entry
            for entry in diff_summary
            if entry["id"] == definition.definition_id and _is_triggering_action(entry["action"])
        ),
        None,
    )
    if matched_entry is None:
        return PredicateOutcome(matched=False)

    changed_fields = ", ".join(
        element["name"] for element in matched_entry["elements"] if _is_triggering_action(element["action"])
    )
    detail = f"definition node was modified ({changed_fields})" if changed_fields else "definition node was modified"
    return PredicateOutcome(
        matched=True,
        reason=(
            f"Definition {definition.definition_name} ({definition.definition_id}): {detail} - "
            f"all {definition.instance_noun} of this definition will regenerate."
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
    if definition.dependencies is None:
        legacy_reason = (
            f"Definition {definition.definition_name}: {definition.source_noun} was imported before this feature "
            f"deployed (dependencies=null) - falling back to regenerate-on-any-file-change. The next re-import of "
            f"this {definition.source_noun} will populate its dependency closure."
        )
        return PredicateOutcome(
            matched=repo_diff.has_modifications,
            reason=legacy_reason if repo_diff.has_modifications else None,
        )

    if definition.dependencies_complete is not True:
        incomplete_reason = (
            f"Definition {definition.definition_name}: {definition.source_noun} dependency closure is incomplete "
            f"(dependencies_complete=False) - falling back to regenerate-on-any-file-change."
        )
        return PredicateOutcome(
            matched=repo_diff.has_modifications,
            reason=incomplete_reason if repo_diff.has_modifications else None,
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
        reason=(
            f"Definition {definition.definition_name}: file {files} changed and is in this "
            f"{definition.source_noun}'s dependency closure - all {definition.instance_noun} will regenerate."
        ),
    )


def repo_diff_or_none(branch_diff: ProposedChangeBranchDiff, repository_id: str) -> ProposedChangeRepository | None:
    try:
        return branch_diff.get_repository(repository_id)
    except NodeNotFoundError:
        return None
