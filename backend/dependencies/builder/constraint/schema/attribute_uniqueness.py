from typing import Optional, Union

from infrahub.core.branch import Branch
from infrahub.core.validators.attribute.unique import AttributeUniquenessChecker
from infrahub.database import InfrahubDatabase

from ....interface import DependencyBuilder


class SchemaAttributeUniqueConstraintDependency(DependencyBuilder[AttributeUniquenessChecker]):
    @classmethod
    def build(cls, db: InfrahubDatabase, branch: Optional[Branch] = None) -> AttributeUniquenessChecker:
        return AttributeUniquenessChecker(db=db, branch=branch)
