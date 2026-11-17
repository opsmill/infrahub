from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from collections.abc import Sequence

    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.schema_change.operations import SchemaOperation


class SchemaOperationsCheck(ABC):
    """Check that the operations built from a schema file rebuild the schema of that file laid over the branch schema.

    No method changes `branch_schema` or `direct_load_schema`.
    """

    @abstractmethod
    def check(
        self,
        *,
        branch_schema: SchemaBranch,
        operations: Sequence[SchemaOperation],
        default_branch_schema: SchemaBranch,
        direct_load_schema: SchemaBranch,
    ) -> None: ...


class NoSchemaOperationsCheck(SchemaOperationsCheck):
    """Check nothing, so that a schema load processes the schema once."""

    @override
    def check(
        self,
        *,
        branch_schema: SchemaBranch,
        operations: Sequence[SchemaOperation],
        default_branch_schema: SchemaBranch,
        direct_load_schema: SchemaBranch,
    ) -> None:
        return
