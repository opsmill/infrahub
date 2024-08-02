from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType, InfrahubKind
from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType  # noqa: TCH001

from ..query.attribute_rename import AttributeInfo, AttributeRenameMigrationQuery
from ..query.node_duplicate import NodeDuplicateMigrationQuery, SchemaNodeInfo
from ..query.relationship_duplicate import RelationshipDuplicateQuery, SchemaRelationshipInfo
from ..query.schema_attribute_update import SchemaAttributeUpdateQuery
from ..shared import GraphMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


# Data Migration
# - Add `CoreGenericAccount` to labels of `CoreAccount` nodes
#   NodeDuplicate query
# - Rename `type` attribute to `account_type`
#   AttributeRename query

# - Rename `coreaccount__internalaccounttoken` relationship to `coregenericaccount__internalaccounttoken`
#   Rename relationship
#     Create DuplicateRelationship query

# Schema migration
# - DONE : Add `CoreGenericAccount` to `inherit_from` value of `SchemaNode` with name value `Account`
# - DONE Rename `type` attribute to `account_type`
# - Remove relationships for attribute that have moved to Generic


class Migration012RenameTypeAttributeData(AttributeRenameMigrationQuery):
    name = "migration_012_rename_attr_type"

    def __init__(self, **kwargs: Any):
        new_attr = AttributeInfo(
            name="account_type",
            node_kind="CoreAccount",
            branch_support=BranchSupportType.AGNOSTIC.value,
        )
        previous_attr = AttributeInfo(
            name="type",
            node_kind="CoreAccount",
            branch_support=BranchSupportType.AGNOSTIC.value,
        )

        branch = Branch(
            name=GLOBAL_BRANCH_NAME,
            status="OPEN",
            description="Global Branch",
            hierarchy_level=1,
            is_global=True,
            sync_with_git=False,
        )

        if "branch" in kwargs:
            del kwargs["branch"]

        super().__init__(new_attr=new_attr, previous_attr=previous_attr, branch=branch, **kwargs)

    def render_match(self) -> str:
        query = """
        // Find all the active nodes
        MATCH (node:%(node_kind)s|Profile%(node_kind)s)
        WHERE exists((node)-[:HAS_ATTRIBUTE]-(:Attribute { name: $prev_attr.name }))
            AND NOT exists((node)-[:HAS_ATTRIBUTE]-(:Attribute { name: $new_attr.name }))

        """ % {"node_kind": self.previous_attr.node_kind}

        return query


class Migration012AddLabelData(NodeDuplicateMigrationQuery):
    name = "migration_012_add_labels"

    def __init__(self, **kwargs: Any):
        new_node = SchemaNodeInfo(
            name="Account",
            namespace="Core",
            branch_support=BranchSupportType.AGNOSTIC.value,
            labels=["CoreAccount", InfrahubKind.GENERICACCOUNT, InfrahubKind.LINEAGEOWNER, InfrahubKind.LINEAGESOURCE],
        )
        previous_node = SchemaNodeInfo(
            name="Account",
            namespace="Core",
            branch_support=BranchSupportType.AGNOSTIC.value,
            labels=["CoreAccount", InfrahubKind.LINEAGEOWNER, InfrahubKind.LINEAGESOURCE],
        )

        branch = Branch(
            name=GLOBAL_BRANCH_NAME,
            status="OPEN",
            description="Global Branch",
            hierarchy_level=1,
            is_global=True,
            sync_with_git=False,
        )

        if "branch" in kwargs:
            del kwargs["branch"]

        super().__init__(new_node=new_node, previous_node=previous_node, branch=branch, **kwargs)

    def render_match(self) -> str:
        query = f"""
        // Find all the active nodes
        MATCH (node:{self.previous_node.kind})
        WHERE NOT "CoreGenericAccount" IN LABELS(node)
        """

        return query


class Migration012RenameTypeAttributeSchema(SchemaAttributeUpdateQuery):
    name = "migration_012_rename_type_attr_schema"
    type: QueryType = QueryType.WRITE
    insert_return = False

    def __init__(self, **kwargs: Any):
        super().__init__(
            attribute_name="name",
            node_name="Account",
            node_namespace="Core",
            new_value="account_type",
            previous_value="type",
            **kwargs,
        )

    def render_match(self) -> str:
        return self._render_match_schema_attribute()


class Migration012RenameRelationshipAccountTokenData(RelationshipDuplicateQuery):
    name = "migration_012_rename_rel_account_token_data"

    def __init__(self, **kwargs: Any):
        new_rel = SchemaRelationshipInfo(
            name="coregenericaccount__internalaccounttoken",
            branch_support=BranchSupportType.AGNOSTIC.value,
            src_peer="CoreAccount",
            dst_peer="InternalAccountToken",
        )
        previous_rel = SchemaRelationshipInfo(
            name="coreaccount__internalaccounttoken",
            branch_support=BranchSupportType.AGNOSTIC.value,
            src_peer="CoreAccount",
            dst_peer="InternalAccountToken",
        )

        branch = Branch(
            name=GLOBAL_BRANCH_NAME,
            status="OPEN",
            description="Global Branch",
            hierarchy_level=1,
            is_global=True,
            sync_with_git=False,
        )

        if "branch" in kwargs:
            del kwargs["branch"]

        super().__init__(new_rel=new_rel, previous_rel=previous_rel, branch=branch, **kwargs)


class Migration012(GraphMigration):
    name: str = "012_convert_account_generic"
    queries: Sequence[type[Query]] = [
        Migration012RenameTypeAttributeSchema,
        Migration012RenameTypeAttributeData,
        Migration012AddLabelData,
        Migration012RenameRelationshipAccountTokenData,
    ]
    minimum_version: int = 11

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        result = MigrationResult()

        return result
