from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.migrations.shared import MigrationInput, MigrationResult, get_migration_console
from infrahub.core.query import Query, QueryType
from infrahub.log import get_logger

from ..shared import ArbitraryMigration

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase

log = get_logger()
console = get_migration_console()

ALL_NULL_PARAMETER_VALUES = [
    '{"id":null,"state":"present"}',
    '{"id":null,"state":"present","regex":null}',
    '{"id":null,"state":"present","regex":null,"min_length":null,"max_length":null}',
]


class FixBranchParametersQuery(Query):
    """Find and fix spurious branch-specific parameters on SchemaAttributes of
    SchemaNode and SchemaGeneric that were incorrectly written by a previous version of Migration056.

    For each affected parameters Attribute:
    - The branch value must be one of the known all-null JSON shapes
    - The previous default-branch value (at branched_from time) must be 'NULL' or one of those shapes
    - Expire the spurious branch edge and create a new one with the previous default value
    """

    name = "fix_branch_parameters"
    type: QueryType = QueryType.WRITE

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        self.params["default_branch"] = registry.default_branch
        self.params["branch_name"] = self.branch.name
        self.params["branch_level"] = self.branch.hierarchy_level
        self.params["branched_from"] = self.branch.get_branched_from()
        self.params["at"] = self.at.to_string()
        self.params["all_null_values"] = ALL_NULL_PARAMETER_VALUES
        self.params["all_null_and_unset_values"] = ["NULL"] + ALL_NULL_PARAMETER_VALUES

        query = """
// ------------------
// Find SchemaNode and SchemaGeneric schema nodes
// ------------------
MATCH (schema_node:SchemaNode)-[e1:HAS_ATTRIBUTE]->(:Attribute {name: "name"})-[e2:HAS_VALUE]->(name_val:AttributeValue)
WHERE name_val.value IN ["Node", "Generic"]
AND e1.status = "active" AND e1.to IS NULL
AND e2.status = "active" AND e2.to IS NULL
WITH DISTINCT schema_node
MATCH (schema_node)-[e3:HAS_ATTRIBUTE]->(:Attribute {name: "namespace"})-[e4:HAS_VALUE]->(ns_val:AttributeValue)
WHERE ns_val.value = "Schema"
AND e3.status = "active" AND e3.to IS NULL
AND e4.status = "active" AND e4.to IS NULL
WITH DISTINCT schema_node
// ------------------
// Find linked SchemaAttribute nodes and their parameters Attribute
// ------------------
MATCH (schema_node)-[e5:IS_RELATED]->(:Relationship {name: "schema__node__attributes"})<-[e6:IS_RELATED]-(schema_attr:SchemaAttribute)
WHERE e5.status = "active" AND e5.to IS NULL
AND e6.status = "active" AND e6.to IS NULL
MATCH (schema_attr)-[e7:HAS_ATTRIBUTE]->(param_attr:Attribute {name: "parameters"})
WHERE e7.status = "active" AND e7.to IS NULL
WITH DISTINCT param_attr

// ------------------
// Get the current branch-specific value
// Only match known all-null JSON shapes
// ------------------
MATCH (param_attr)-[branch_e:HAS_VALUE]->(branch_av:AttributeValue)
WHERE branch_e.branch = $branch_name
AND branch_e.status = "active"
AND branch_e.to IS NULL
AND branch_av.value IN $all_null_values

// ------------------
// Get the previous default-branch value that was active at branched_from time
// Only proceed if it was NULL or an all-null JSON shape
// ------------------
CALL (param_attr) {
    MATCH (param_attr)-[default_e:HAS_VALUE]->(default_av:AttributeValue)
    WHERE default_e.branch = $default_branch
    AND default_e.status = "active"
    AND default_e.from < $branched_from
    AND (default_e.to IS NULL OR default_e.to > $branched_from)
    AND default_av.value IN $all_null_and_unset_values
    RETURN default_av
    LIMIT 1
}

// ------------------
// Expire the spurious branch edge and create a corrected one
// ------------------
WITH param_attr, branch_e, default_av
SET branch_e.to = $at
WITH param_attr, branch_e, default_av
CREATE (param_attr)-[new_has_value:HAS_VALUE]->(default_av)
SET new_has_value = properties(branch_e)
SET new_has_value.from = $at, new_has_value.to = NULL
        """
        self.add_to_query(query)
        self.return_labels = ["param_attr"]


class Migration068(ArbitraryMigration):
    """Clean up possible spurious edges created by old version of Migration056 on SchemaAttribute parameters

    The old version of Migration056 was too broad in what it saved to the database and could update the "parameters"
    attribute of SchemaAttribute objects from NULL to a JSON blobs. This is technically correct b/c parameters
    properties should be saved as JSON objects, but this could cause conflicts if the "parameters" were also updated
    on the default branch. Fortunately, Migration056 only targeted the SchemaNode and SchemaGeneric schemas, so the
    possible affected SchemaAttribute objects are very limited.
    """

    name: str = "068_cleanup_branch_schema_parameters"
    minimum_version: int = 67

    async def validate_migration(self, db: InfrahubDatabase) -> MigrationResult:  # noqa: ARG002
        return MigrationResult()

    async def execute(self, migration_input: MigrationInput) -> MigrationResult:
        db = migration_input.db
        at = migration_input.at

        console.log("[bold]Cleaning up spurious branch schema attribute parameters from Migration056[/bold]")

        branches = await Branch.get_list(db=db)
        branches = [b for b in branches if not b.is_default and not b.is_global and not b.is_terminal]

        if not branches:
            console.log("No open user branches found, nothing to clean up")
            return MigrationResult()

        console.log(f"Checking {len(branches)} open user branches")

        for branch in branches:
            fix_query = await FixBranchParametersQuery.init(db=db, branch=branch, at=at)
            await fix_query.execute(db=db)
            if fix_query.num_of_results:
                console.log(f"Branch '{branch.name}': fixed {fix_query.num_of_results} spurious parameters")

        console.log("[bold green]Migration completed successfully[/bold green]")
        return MigrationResult()
