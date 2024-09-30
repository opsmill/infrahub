from typing import Any

from infrahub.core.constants import DiffAction

from ..model.path import ConflictSelection, EnrichedDiffRoot, EnrichedDiffConflict



class DiffMergeSerializer:
    def _get_action(self, action: DiffAction, conflict: EnrichedDiffConflict | None) -> DiffAction:
        if not conflict:
            return action
        if conflict.selected_branch is ConflictSelection.BASE_BRANCH:
            return conflict.base_branch_action
        elif conflict.selected_branch is ConflictSelection.DIFF_BRANCH:
            return conflict.diff_branch_action
        raise ValueError(f"conflict {conflict.uuid} does not have a branch selection")

    async def serialize(self, diff: EnrichedDiffRoot) -> list[dict[str, Any]]:
        serialized_node_diffs = []
        for node in diff.nodes:
            node_action = self._get_action(action=node.action, conflict=node.conflict)
            serialized_node_diffs.append(
                {
                    "action": str(node_action.value).upper(),
                    "uuid": node.uuid,
                }
            )
        return serialized_node_diffs
