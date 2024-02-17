from typing import Optional, Union

from infrahub.core.branch import Branch
from infrahub.core.validators.relationship.optional import RelationshipOptionalChecker
from infrahub.database import InfrahubDatabase

from ....interface import DependencyBuilder


class SchemaRelationshipOptionalConstraintDependency(DependencyBuilder[RelationshipOptionalChecker]):
    @classmethod
    def build(cls, db: InfrahubDatabase, branch: Optional[Branch] = None) -> RelationshipOptionalChecker:
        return RelationshipOptionalChecker(db=db, branch=branch)
