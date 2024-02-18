from typing import Optional

from infrahub.core.branch import Branch
from infrahub.core.validators.aggregated_checker import AggregatedConstraintChecker
from infrahub.database import InfrahubDatabase

from ....interface import DependencyBuilder
from .attribute_regex import SchemaAttributeRegexConstraintDependency
from .attribute_uniqueness import SchemaAttributeUniqueConstraintDependency
from .relationship_optional import SchemaRelationshipOptionalConstraintDependency
from .uniqueness import SchemaUniquenessConstraintDependency


class AggregatedSchemaConstraintsDependency(DependencyBuilder[AggregatedConstraintChecker]):
    @classmethod
    def build(cls, db: InfrahubDatabase, branch: Optional[Branch] = None) -> AggregatedConstraintChecker:
        return AggregatedConstraintChecker(
            constraints=[
                SchemaUniquenessConstraintDependency.build(db=db, branch=branch),
                SchemaRelationshipOptionalConstraintDependency.build(db=db, branch=branch),
                SchemaAttributeRegexConstraintDependency.build(db=db, branch=branch),
                SchemaAttributeUniqueConstraintDependency.build(db=db, branch=branch),
            ],
            db=db,
            branch=branch,
        )
