from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch import SchemaBranch


class SchemaBranchValidator:
    @abstractmethod
    def check(self, schema_branch: SchemaBranch) -> None:
        raise NotImplementedError()
