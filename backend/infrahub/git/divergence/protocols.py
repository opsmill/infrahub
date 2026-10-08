from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable

    from infrahub.git.divergence.models import RewriteRecord


class AncestryGateway(Protocol):
    """Answers ancestry questions about one repository's object database.

    Implementations raise RepositoryError for every git failure, so the logic above them handles
    one exception type and imports no git library.
    """

    def require_commit(self, commit: str) -> None:
        """Raise unless the identifier is well formed. A commit that is absent passes."""
        ...

    def require_present_commit(self, commit: str) -> None:
        """Raise unless the object database holds that commit."""
        ...

    def is_ancestor(self, ancestor_commit: str, descendant_commit: str) -> bool: ...

    def has_commit(self, commit: str) -> bool: ...


class RepositoryRecordStore(Protocol):
    """Writes the rewrite record a repository holds on one Infrahub branch.

    Implementations raise RepositoryError for every failure, chained from the error that caused it, so
    the logic above them handles one exception type, imports no client library, and can still describe
    the cause.
    """

    async def write_record(
        self, repository_id: str, infrahub_branch_name: str, build_record: Callable[[int | None], RewriteRecord]
    ) -> None:
        """Read the rewrite count the branch holds, and write the record that ``build_record`` makes from it."""
        ...
