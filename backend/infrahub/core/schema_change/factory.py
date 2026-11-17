from __future__ import annotations

from infrahub.core.schema_change.applier import SchemaChangeApplier
from infrahub.core.schema_change.candidate import SchemaCandidateBuilder
from infrahub.core.schema_change.candidate_comparer import SchemaCandidateComparer
from infrahub.core.schema_change.operation_builder import SchemaOperationBuilder


def build_schema_candidate_builder() -> SchemaCandidateBuilder:
    return SchemaCandidateBuilder(
        operation_builder=SchemaOperationBuilder(),
        applier=SchemaChangeApplier(),
        comparer=SchemaCandidateComparer(),
    )
