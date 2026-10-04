from __future__ import annotations

from typing import Protocol


class AncestryGateway(Protocol):
    """Answers ancestry questions about one repository's object database.

    Implementations raise RepositoryError for every git failure, so the logic above them handles
    one exception type and imports no git library.
    """

    def is_ancestor(self, ancestor_commit: str, descendant_commit: str) -> bool: ...

    def has_commit(self, commit: str) -> bool: ...
