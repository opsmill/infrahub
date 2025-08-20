from infrahub.core.constants import InfrahubKind
from infrahub.core.integrity.object_conflict.conflict_recorder import ObjectConflictValidatorRecorder
from infrahub.dependencies.interface import DependencyBuilder, DependencyBuilderContext


class DataCheckConflictRecorderDependency(DependencyBuilder[ObjectConflictValidatorRecorder]):
    @classmethod
    def build(cls, context: DependencyBuilderContext) -> ObjectConflictValidatorRecorder:
        return ObjectConflictValidatorRecorder(
            db=context.db,
            validator_kind=InfrahubKind.DATAVALIDATOR,
            validator_label="Data Integrity",
            check_schema_kind=InfrahubKind.DATACHECK,
        )
