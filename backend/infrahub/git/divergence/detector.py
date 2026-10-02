from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.git.divergence.models import RefClassification, RefDivergence

if TYPE_CHECKING:
    from infrahub.git.divergence.gateway import AncestryGateway


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
        branch_name: str,
        infrahub_branch_name: str,
        imported_commit: str | None,
        remote_head: str | None,
        target_changed: bool,
    ) -> RefDivergence:
        """Decide what happened to one tracked ref.

        Args:
            imported_commit: The commit recorded in the graph, never the local worktree head.
            target_changed: Whether the repository was re-pointed at a different tracking target.
                The caller owns the suppression marker and supplies the answer.

        Raises:
            RepositoryError: When git could not answer the ancestry question.

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

        return self._classify_by_ancestry(
            imported_commit=imported_commit, remote_head=remote_head, target_changed=target_changed
        )

    def _classify_by_ancestry(self, imported_commit: str, remote_head: str, target_changed: bool) -> RefClassification:
        # Asked before the ancestry questions because those cannot be answered once the object is
        # gone: the ancestry call raises instead.
        if not self.gateway.has_commit(commit=imported_commit):
            return self._diverged(target_changed=target_changed)

        if self.gateway.is_ancestor(ancestor_commit=imported_commit, descendant_commit=remote_head):
            return RefClassification.FAST_FORWARD

        if self.gateway.is_ancestor(ancestor_commit=remote_head, descendant_commit=imported_commit):
            return RefClassification.LOCAL_AHEAD

        return self._diverged(target_changed=target_changed)

    def _diverged(self, target_changed: bool) -> RefClassification:
        return RefClassification.RETARGET if target_changed else RefClassification.REWRITE
