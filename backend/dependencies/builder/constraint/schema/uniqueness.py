from typing import Optional, Union

from infrahub.core.branch import Branch
from infrahub.core.validators.uniqueness.checker import UniquenessChecker
from infrahub.database import InfrahubDatabase

from ....interface import DependencyBuilder


class SchemaUniquenessConstraintDependency(DependencyBuilder[UniquenessChecker]):
    @classmethod
    def build(cls, db: InfrahubDatabase, branch: Optional[Branch] = None) -> UniquenessChecker:
        return UniquenessChecker(db=db, branch=branch)
