from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from infrahub.core.branch import Branch
from infrahub.core.constants import (
    GLOBAL_BRANCH_NAME,
    BranchSupportType,
    InfrahubKind,
    RelationshipStatus,
    RepositoryInternalStatus,
)
from infrahub.core.migrations.shared import MigrationResult
from infrahub.core.query import Query, QueryType
from infrahub.core.timestamp import Timestamp

from ..query.attribute_add import AttributeAddQuery
from ..query.delete_element_in_schema import DeleteElementInSchemaQuery
from ..shared import GraphMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

default_branch = Branch(
    name="main",
    status="OPEN",
    description="Default Branch",
    hierarchy_level=1,
    is_global=False,
    is_default=True,
    sync_with_git=False,
)


class Migration013ConvertCoreRepositoryWithCred(Query):
    name = "migration_013_convert_repository_with_cred"
    type = QueryType.WRITE

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        at = Timestamp()
        filters, params = at.get_query_filter_path()

        global_branch = Branch(
            name=GLOBAL_BRANCH_NAME,
            status="OPEN",
            description="Global Branch",
            hierarchy_level=1,
            is_global=True,
            sync_with_git=False,
        )
        self.params.update(params)

        self.params["rel_props_new"] = {
            "branch": global_branch.name,
            "branch_level": global_branch.hierarchy_level,
            "status": RelationshipStatus.ACTIVE.value,
            "from": self.at.to_string(),
        }

        self.params["rel_props_del"] = {
            "branch": global_branch.name,
            "branch_level": global_branch.hierarchy_level,
            "status": RelationshipStatus.DELETED.value,
            "from": self.at.to_string(),
        }

        self.params["cred_node_props"] = {
            "branch_support": BranchSupportType.AGNOSTIC.value,
            "kind": InfrahubKind.PASSWORDCREDENTIAL,
            "namespace": "Core",
        }

        self.params["current_time"] = self.at.to_string()
        self.params["is_protected_default"] = False
        self.params["is_visible_default"] = True
        self.params["branch_support"] = BranchSupportType.AGNOSTIC.value

        self.params["rel_identifier"] = "gitrepository__credential"

        # ruff: noqa: E501
        query = """
        // --------------------------------
        // Identify the git repositories to convert
        // --------------------------------
        MATCH path = (root:Root)<-[r:IS_PART_OF]-(node:%(git_repository)s)-[r9:HAS_ATTRIBUTE]-(a:Attribute)-[:HAS_VALUE]-(av:AttributeValue)
        WHERE a.name in ["username", "password"]
            AND av.value <> "NULL"
            AND all(r IN relationships(path) WHERE %(filters)s AND r.status = "active")
        WITH DISTINCT(node) as git_repo, root
        // --------------------------------
        // Prepare some nodes we'll need later
        // --------------------------------
        MERGE (is_protected_value:Boolean { value: $is_protected_default })
        MERGE (is_visible_value:Boolean { value: $is_visible_default })
        WITH git_repo, root, is_protected_value, is_visible_value
        // --------------------------------
        // Retrieve the name of the current repository
        // --------------------------------
        MATCH (git_repo)-[:HAS_ATTRIBUTE]-(git_attr_name:Attribute)-[:HAS_VALUE]->(git_name_value:AttributeValue)
        WHERE git_attr_name.name = "name"
        CALL {
            WITH git_repo
            MATCH path1 = (git_repo)-[r1:HAS_ATTRIBUTE]-(git_attr_name2:Attribute)-[r2:HAS_VALUE]->(git_name_value2:AttributeValue)
            WHERE git_attr_name2.name = "name"
              AND all(r IN relationships(path1) WHERE %(filters)s)
            RETURN git_repo as n1, r1 as r11, r2 as r22, git_name_value2 as av1
            ORDER BY r1.branch_level DESC, r1.from DESC
            LIMIT 1
        }
        WITH  n1 as git_repo, r11 as r1, r22 as r2, av1 as git_name_value, root, is_protected_value, is_visible_value
        WHERE r1.status = "active" AND r2.status = "active"
        WITH DISTINCT(git_repo) as git_repo, root, is_protected_value, is_visible_value, git_name_value
        // --------------------------------
        // Create new CorePasswordCredential node
        // --------------------------------
        CREATE (cred:Node:%(credential)s:%(password_credential)s $cred_node_props )-[:IS_PART_OF $rel_props_new ]->(root)
        %(cred_guid)s
        // attribute: name
        CREATE (attr_name:Attribute { name: "name", branch_support: $branch_support })
        CREATE (attr_name)<-[:HAS_ATTRIBUTE $rel_props_new ]-(cred)
        CREATE (attr_name)-[:HAS_VALUE $rel_props_new ]->(git_name_value)
        CREATE (attr_name)-[:IS_PROTECTED $rel_props_new]->(is_protected_value)
        CREATE (attr_name)-[:IS_VISIBLE $rel_props_new]->(is_visible_value)
        // attribute: label
        CREATE (attr_lbl:Attribute { name: "label", branch_support: $branch_support })
        CREATE (attr_lbl)<-[:HAS_ATTRIBUTE $rel_props_new ]-(cred)
        CREATE (attr_lbl)-[:HAS_VALUE $rel_props_new ]->(git_name_value)
        CREATE (attr_lbl)-[:IS_PROTECTED $rel_props_new]->(is_protected_value)
        CREATE (attr_lbl)-[:IS_VISIBLE $rel_props_new]->(is_visible_value)
        // attribute: description
        CREATE (attr_desc:Attribute { name: "description", branch_support: $branch_support })
        MERGE (av_desc:AttributeValue { value: "Credential for " + git_name_value.value, is_default: true })
        CREATE (attr_desc)<-[:HAS_ATTRIBUTE $rel_props_new ]-(cred)
        CREATE (attr_desc)-[:HAS_VALUE $rel_props_new ]->(av_desc)
        CREATE (attr_desc)-[:IS_PROTECTED $rel_props_new]->(is_protected_value)
        CREATE (attr_desc)-[:IS_VISIBLE $rel_props_new]->(is_visible_value)
        %(attr_name_guid)s
        %(attr_label_guid)s
        %(attr_desc_guid)s
        WITH git_repo, cred
        // --------------------------------
        // Move Username and Password to the new credential node
        // --------------------------------
        MATCH (git_repo)-[r1:HAS_ATTRIBUTE]-(git_attr:Attribute)
        WHERE git_attr.name IN ["username", "password"]
        CREATE (cred)-[:HAS_ATTRIBUTE $rel_props_new ]->(git_attr)
        CREATE (git_repo)-[:HAS_ATTRIBUTE $rel_props_del ]->(git_attr)
        SET r1.to = $current_time
        WITH DISTINCT(git_repo) as git_repo, cred
        // --------------------------------
        // Create a new relationship between git_repo and Cred
        // --------------------------------
        CREATE (rel:Relationship { name: $rel_identifier, branch_support: $branch_support })
        %(rel_guid)s
        CREATE (git_repo)-[:IS_RELATED $rel_props_new]->(rel)<-[:IS_RELATED $rel_props_new]-(cred)
        """ % {
            "filters": filters,
            "cred_guid": db.render_uuid_generation(node_label="cred", node_attr="uuid", index=1),
            "attr_name_guid": db.render_uuid_generation(node_label="attr_name", node_attr="uuid", index=2),
            "attr_label_guid": db.render_uuid_generation(node_label="attr_lbl", node_attr="uuid", index=3),
            "attr_desc_guid": db.render_uuid_generation(node_label="attr_desc", node_attr="uuid", index=4),
            "rel_guid": db.render_uuid_generation(node_label="rel", node_attr="uuid", index=5),
            "git_repository": InfrahubKind.GENERICREPOSITORY,
            "credential": InfrahubKind.CREDENTIAL,
            "password_credential": InfrahubKind.PASSWORDCREDENTIAL,
        }
        self.add_to_query(query)
        self.return_labels = ["git_repo", "cred"]


class Migration013ConvertCoreRepositoryWithoutCred(Query):
    name = "migration_013_convert_repository_without_cred"
    type = QueryType.WRITE

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        at = Timestamp()
        filters, params = at.get_query_filter_path()

        global_branch = Branch(
            name=GLOBAL_BRANCH_NAME,
            status="OPEN",
            description="Global Branch",
            hierarchy_level=1,
            is_global=True,
            sync_with_git=False,
        )
        self.params.update(params)

        self.params["rel_props_del"] = {
            "branch": global_branch.name,
            "branch_level": global_branch.hierarchy_level,
            "status": RelationshipStatus.DELETED.value,
            "from": self.at.to_string(),
        }

        self.params["current_time"] = self.at.to_string()

        # ruff: noqa: E501
        query = """
        // --------------------------------
        // Identify the git repositories to convert
        // --------------------------------
        MATCH path = (node:%(git_repository)s)-[r9:HAS_ATTRIBUTE]-(a:Attribute)-[:HAS_VALUE]-(av:AttributeValue)
        WHERE a.name in ["username", "password"]
            AND av.value = "NULL"
            AND all(r IN relationships(path) WHERE %(filters)s AND r.status = "active")
        CALL {
            WITH node
            MATCH (root:Root)<-[r:IS_PART_OF]-(node)
            WHERE %(filters)s
            RETURN node as n1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as node, r1 as rb
        WHERE rb.status = "active"
        WITH DISTINCT(node) as git_repo
        // --------------------------------
        // Delete Username and Password attributes
        // --------------------------------
        MATCH (git_repo)-[r1:HAS_ATTRIBUTE]-(git_attr:Attribute)
        WHERE git_attr.name IN ["username", "password"]
        CREATE (git_repo)-[:HAS_ATTRIBUTE $rel_props_del ]->(git_attr)
        SET r1.to = $current_time
        WITH DISTINCT(git_repo) as git_repo
        """ % {
            "filters": filters,
            "git_repository": InfrahubKind.GENERICREPOSITORY,
        }
        self.add_to_query(query)
        self.return_labels = ["git_repo"]


class Migration013DeleteUsernamePasswordGenericSchema(DeleteElementInSchemaQuery):
    name = "migration_013_delete_username_password_schema"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, **kwargs: Any):
        kwargs.pop("branch", None)

        super().__init__(
            element_names=["username", "password"],
            node_name="GenericRepository",
            node_namespace="Core",
            branch=default_branch,
            **kwargs,
        )


class Migration013DeleteUsernamePasswordReadWriteSchema(DeleteElementInSchemaQuery):
    name = "migration_013_delete_username_password_schema"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, **kwargs: Any):
        kwargs.pop("branch", None)

        super().__init__(
            element_names=["username", "password"],
            node_name="Repository",
            node_namespace="Core",
            branch=default_branch,
            **kwargs,
        )


class Migration013DeleteUsernamePasswordReadOnlySchema(DeleteElementInSchemaQuery):
    name = "migration_013_delete_username_password_schema"
    type = QueryType.WRITE
    insert_return = False

    def __init__(self, **kwargs: Any):
        kwargs.pop("branch", None)

        super().__init__(
            element_names=["username", "password"],
            node_name="ReadOnlyRepository",
            node_namespace="Core",
            branch=default_branch,
            **kwargs,
        )


class Migration013AddInternalStatusData(AttributeAddQuery):
    type = QueryType.WRITE

    def __init__(self, **kwargs: Any):
        kwargs.pop("branch", None)

        super().__init__(
            node_kind="CoreGenericRepository",
            attribute_name="internal_status",
            attribute_kind="Dropdown",
            branch_support=BranchSupportType.LOCAL.value,
            default_value=RepositoryInternalStatus.ACTIVE.value,
            branch=default_branch,
            **kwargs,
        )


class Migration013(GraphMigration):
    name: str = "013_convert_git_password_credential"
    queries: Sequence[type[Query]] = [
        Migration013ConvertCoreRepositoryWithCred,
        Migration013ConvertCoreRepositoryWithoutCred,
        Migration013DeleteUsernamePasswordGenericSchema,
        Migration013DeleteUsernamePasswordReadWriteSchema,
        Migration013DeleteUsernamePasswordReadOnlySchema,
        Migration013AddInternalStatusData,
    ]
    minimum_version: int = 12

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        result = MigrationResult()

        return result
