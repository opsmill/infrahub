from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.git.divergence.models import RefClassification, RefDivergence

if TYPE_CHECKING:
    from infrahub.git.divergence.protocols import AncestryGateway


class RemoteDivergenceDetector:
    """Classifies a tracked ref's remote head against the commit recorded in the graph.

    The result decides whether to record a rewrite. It does not decide whether this worker's
    worktree must move: that compares the worktree head against the remote head instead, and a
    worker whose graph is already current can still need to reset.
    """

    def __init__(self, gateway: AncestryGateway) -> None:
        self.gateway = gateway

    def classify(
        self,
        *,
        branch_name: str,
        infrahub_branch_name: str,
        imported_commit: str | None,
        remote_head: str | None,
        target_changed: bool,
    ) -> RefDivergence:
        """Decide what happened to one tracked ref.

        Args:
            target_changed: Whether the repository was re-pointed at a different tracking target.

        Raises:
            RepositoryError: When a comparison is needed and git cannot complete it, either
                because the imported commit is a malformed identifier or because the presence or
                ancestry check failed. A ref the remote still carries unchanged needs no
                comparison and raises nothing.

        """
        return RefDivergence(
            branch_name=branch_name,
            infrahub_branch_name=infrahub_branch_name,
            imported_commit=imported_commit,
            remote_head=remote_head,
            classification=self._classify(
                imported_commit=imported_commit, remote_head=remote_head, target_changed=target_changed
            ),
        )

    def _classify(
        self, imported_commit: str | None, remote_head: str | None, target_changed: bool
    ) -> RefClassification:
        if remote_head is None:
            return RefClassification.REMOTE_ABSENT if imported_commit is not None else RefClassification.UNCHANGED

        if imported_commit is None:
            return RefClassification.FAST_FORWARD

        if remote_head == imported_commit:
            return RefClassification.UNCHANGED

        # Asked before the ancestry question because it cannot be answered once the object is
        # gone: the ancestry call raises instead.
        if not self.gateway.has_commit(commit=imported_commit):
            return self._diverged(target_changed=target_changed)

        if self.gateway.is_ancestor(ancestor_commit=imported_commit, descendant_commit=remote_head):
            return RefClassification.FAST_FORWARD

        # No path writes a graph commit the remote never had, so anything left here lost the
        # imported commit rather than running ahead of it.
        return self._diverged(target_changed=target_changed)

    def _diverged(self, target_changed: bool) -> RefClassification:
        return RefClassification.RETARGET if target_changed else RefClassification.REWRITE
