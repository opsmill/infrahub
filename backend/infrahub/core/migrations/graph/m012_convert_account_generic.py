from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.branch import Branch
from infrahub.core.constants import GLOBAL_BRANCH_NAME, BranchSupportType, InfrahubKind
from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType  # noqa: TCH001

from ..query.attribute_rename import AttributeInfo, AttributeRenameQuery
from ..query.delete_element_in_schema import DeleteElementInSchemaQuery
from ..query.node_duplicate import NodeDuplicateQuery, SchemaNodeInfo
from ..query.relationship_duplicate import RelationshipDuplicateQuery, SchemaRelationshipInfo
from ..query.schema_attribute_update import SchemaAttributeUpdateQuery
from ..shared import GraphMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


global_branch = Branch(
    name=GLOBAL_BRANCH_NAME,
    status="OPEN",
    description="Global Branch",
    hierarchy_level=1,
    is_global=True,
    sync_with_git=False,
)

default_branch = Branch(
    name="main",
    status="OPEN",
    description="Default Branch",
    hierarchy_level=1,
    is_global=False,
    is_default=True,
    sync_with_git=False,
)


class Migration012RenameTypeAttributeData(AttributeRenameQuery):
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

        if "branch" in kwargs:
            del kwargs["branch"]

        super().__init__(new_attr=new_attr, previous_attr=previous_attr, branch=global_branch, **kwargs)

    def render_match(self) -> str:
        query = """
        // Find all the active nodes
        MATCH (node:%(node_kind)s|Profile%(node_kind)s)
        WHERE exists((node)-[:HAS_ATTRIBUTE]-(:Attribute { name: $prev_attr.name }))
            AND NOT exists((node)-[:HAS_ATTRIBUTE]-(:Attribute { name: $new_attr.name }))

        """ % {"node_kind": self.previous_attr.node_kind}

        return query


class Migration012AddLabelData(NodeDuplicateQuery):
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
            name="account__token",
            branch_support=BranchSupportType.AGNOSTIC.value,
            src_peer=InfrahubKind.ACCOUNT,
            dst_peer=InfrahubKind.ACCOUNTTOKEN,
        )
        previous_rel = SchemaRelationshipInfo(
            name="coreaccount__internalaccounttoken",
            branch_support=BranchSupportType.AGNOSTIC.value,
            src_peer=InfrahubKind.ACCOUNT,
            dst_peer=InfrahubKind.ACCOUNTTOKEN,
        )

        if "branch" in kwargs:
            del kwargs["branch"]

        super().__init__(new_rel=new_rel, previous_rel=previous_rel, branch=global_branch, **kwargs)


class Migration012RenameRelationshipRefreshTokenData(RelationshipDuplicateQuery):
    name = "migration_012_rename_rel_refresh_token_data"

    def __init__(self, **kwargs: Any):
        new_rel = SchemaRelationshipInfo(
            name="account__refreshtoken",
            branch_support=BranchSupportType.AGNOSTIC.value,
            src_peer=InfrahubKind.ACCOUNT,
            dst_peer=InfrahubKind.REFRESHTOKEN,
        )
        previous_rel = SchemaRelationshipInfo(
            name="coreaccount__internalrefreshtoken",
            branch_support=BranchSupportType.AGNOSTIC.value,
            src_peer=InfrahubKind.ACCOUNT,
            dst_peer=InfrahubKind.REFRESHTOKEN,
        )

        if "branch" in kwargs:
            del kwargs["branch"]

        super().__init__(new_rel=new_rel, previous_rel=previous_rel, branch=global_branch, **kwargs)


class Migration012RenameRelationshipThreadData(RelationshipDuplicateQuery):
    name = "migration_012_rename_rel_thread_data"

    def __init__(self, **kwargs: Any):
        new_rel = SchemaRelationshipInfo(
            name="thread__account",
            branch_support=BranchSupportType.AGNOSTIC.value,
            src_peer=InfrahubKind.ACCOUNT,
            dst_peer=InfrahubKind.THREAD,
        )
        previous_rel = SchemaRelationshipInfo(
            name="coreaccount__corethread",
            branch_support=BranchSupportType.AGNOSTIC.value,
            src_peer=InfrahubKind.ACCOUNT,
            dst_peer=InfrahubKind.THREAD,
        )

        if "branch" in kwargs:
            del kwargs["branch"]

        super().__init__(new_rel=new_rel, previous_rel=previous_rel, branch=global_branch, **kwargs)


class Migration012RenameRelationshipCommentData(RelationshipDuplicateQuery):
    name = "migration_012_rename_rel_comment_data"

    def __init__(self, **kwargs: Any):
        new_rel = SchemaRelationshipInfo(
            name="comment__account",
            branch_support=BranchSupportType.AGNOSTIC.value,
            src_peer=InfrahubKind.ACCOUNT,
            dst_peer=InfrahubKind.COMMENT,
        )
        previous_rel = SchemaRelationshipInfo(
            name="coreaccount__corecomment",
            branch_support=BranchSupportType.AGNOSTIC.value,
            src_peer=InfrahubKind.ACCOUNT,
            dst_peer=InfrahubKind.COMMENT,
        )

        if "branch" in kwargs:
            del kwargs["branch"]

        super().__init__(new_rel=new_rel, previous_rel=previous_rel, branch=default_branch, **kwargs)


class Migration012DeleteOldElementsSchema(DeleteElementInSchemaQuery):
    name = "migration_012_delete_old_elements_schema"
    type: QueryType = QueryType.WRITE
    insert_return = False

    def __init__(self, **kwargs: Any):
        if "branch" in kwargs:
            del kwargs["branch"]

        super().__init__(
            element_names=["name", "password", "label", "description", "type", "role", "tokens"],
            node_name="Account",
            node_namespace="Core",
            branch=default_branch,
            **kwargs,
        )


class Migration012UpdateDisplayLabels(SchemaAttributeUpdateQuery):
    name = "migration_012_display_labels"
    type: QueryType = QueryType.WRITE
    insert_return = False

    def __init__(self, **kwargs: Any):
        if "branch" in kwargs:
            del kwargs["branch"]

        super().__init__(
            attribute_name="display_labels",
            node_name="Account",
            node_namespace="Core",
            new_value="NULL",
            **kwargs,
        )


class Migration012UpdateOrderBy(SchemaAttributeUpdateQuery):
    name = "migration_012_order_by"
    type: QueryType = QueryType.WRITE
    insert_return = False

    def __init__(self, **kwargs: Any):
        if "branch" in kwargs:
            del kwargs["branch"]

        super().__init__(
            attribute_name="order_by",
            node_name="Account",
            node_namespace="Core",
            new_value="NULL",
            **kwargs,
        )


class Migration012UpdateDefaultFilter(SchemaAttributeUpdateQuery):
    name = "migration_012_reset_default_filter"
    type: QueryType = QueryType.WRITE
    insert_return = False

    def __init__(self, **kwargs: Any):
        if "branch" in kwargs:
            del kwargs["branch"]

        super().__init__(
            attribute_name="default_filter",
            node_name="Account",
            node_namespace="Core",
            new_value="NULL",
            **kwargs,
        )


class Migration012UpdateHFID(SchemaAttributeUpdateQuery):
    name = "migration_012_reset_hfid"
    type: QueryType = QueryType.WRITE
    insert_return = False

    def __init__(self, **kwargs: Any):
        if "branch" in kwargs:
            del kwargs["branch"]

        super().__init__(
            attribute_name="human_friendly_id",
            node_name="Account",
            node_namespace="Core",
            new_value="NULL",
            **kwargs,
        )


class Migration012(GraphMigration):
    name: str = "012_convert_account_generic"
    queries: Sequence[type[Query]] = [
        Migration012DeleteOldElementsSchema,
        Migration012RenameTypeAttributeData,
        Migration012AddLabelData,
        Migration012RenameRelationshipAccountTokenData,
        Migration012RenameRelationshipRefreshTokenData,
        Migration012RenameRelationshipThreadData,
        Migration012RenameRelationshipCommentData,
        Migration012UpdateDefaultFilter,
        Migration012UpdateOrderBy,
        Migration012UpdateDisplayLabels,
        Migration012UpdateHFID,
    ]
    minimum_version: int = 11

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:
        result = MigrationResult()

        return result
