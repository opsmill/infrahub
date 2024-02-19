from typing import Optional

from infrahub.core.branch import Branch
from infrahub.core.validators.attribute.regex import AttributeRegexChecker
from infrahub.database import InfrahubDatabase

from ....interface import DependencyBuilder


class SchemaAttributeRegexConstraintDependency(DependencyBuilder[AttributeRegexChecker]):
    @classmethod
    def build(cls, db: InfrahubDatabase, branch: Optional[Branch] = None) -> AttributeRegexChecker:
        return AttributeRegexChecker(db=db, branch=branch)
