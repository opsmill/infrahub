from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.regeneration.models import DefinitionSelect
from infrahub.core.regeneration.predicates import definition_changed, query_changed, reads_kind

from .models import GateResult

if TYPE_CHECKING:
    import logging

    from infrahub_sdk.diff import NodeDiff

    from .models import DefinitionModel


class DefinitionGate:
    """Decide whether a merge diff requires a definition to regenerate and whether that spans every member.

    Every uncertain signal widens the selection: a query or definition change forces all members,
    and a change touching the target group selects the definition even when no queried field moved.
    """

    def __init__(self, log: logging.Logger | logging.LoggerAdapter[logging.Logger]) -> None:
        self.log = log

    def evaluate(
        self,
        *,
        definition: DefinitionModel,
        diff_summary: list[NodeDiff],
        modified_kinds: list[str],
        group_id: str,
    ) -> GateResult:
        query_outcome = query_changed(definition=definition, diff_summary=diff_summary)
        definition_outcome = definition_changed(definition=definition, diff_summary=diff_summary)
        for outcome in (query_outcome, definition_outcome):
            if outcome.reason is not None:
                self.log.debug(outcome.reason)
        regenerate_all_members = query_outcome.matched or definition_outcome.matched

        matches_modified_kind = any(reads_kind(definition, changed_model) for changed_model in modified_kinds)

        select = DefinitionSelect.NONE
        select = select.add_flag(current=select, flag=DefinitionSelect.QUERY_CHANGED, condition=query_outcome.matched)
        select = select.add_flag(
            current=select, flag=DefinitionSelect.DEFINITION_CHANGED, condition=definition_outcome.matched
        )
        select = select.add_flag(current=select, flag=DefinitionSelect.MODIFIED_KINDS, condition=matches_modified_kind)

        # A membership-only change surfaces as the group node appearing in the diff.
        group_membership = any(entry["id"] == group_id for entry in diff_summary)
        selected = bool(select) or group_membership
        if selected:
            self.log.debug(f"Selecting {definition.definition_name} for regeneration: {select.log_line}")
        return GateResult(regenerate_all_members=regenerate_all_members, selected=selected)
