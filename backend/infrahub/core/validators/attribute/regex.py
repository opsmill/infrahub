from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from infrahub.core.constants import PathType
from infrahub.core.path import DataPath, GroupedDataPaths

from ..interface import ConstraintCheckerInterface
from ..shared import AttributeSchemaValidatorQuery

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.message_bus.messages.schema_validator_path import SchemaValidatorPath


class AttributeRegexUpdateValidatorQuery(AttributeSchemaValidatorQuery):
    name: str = "attribute_constraints_regex_validator"

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Dict[str, Any]) -> None:
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["node_kind"] = self.node_schema.kind
        self.params["attr_name"] = self.attribute_schema.name
        self.params["attr_value_regex"] = self.attribute_schema.regex

        query = """
        MATCH p = (n:Node)
        WHERE $node_kind IN LABELS(n)
        CALL {
            WITH n
            MATCH (root:Root)<-[r:IS_PART_OF]-(n)
            WHERE %(branch_filter)s
            RETURN n as n1, r as r1
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n1 as n, r1 as rb
        WHERE rb.status = "active"
        MATCH path = (n)-[:HAS_ATTRIBUTE]-(:Attribute { name: $attr_name } )-[:HAS_VALUE]-(av:AttributeValue)
        WHERE NOT av.value =~ $attr_value_regex AND all(r IN relationships(path) WHERE (%(branch_filter)s))
        """ % {"branch_filter": branch_filter}

        self.add_to_query(query)
        self.return_labels = ["n.uuid", "av.value", "relationships(path)[-1] as value_relationship"]

    async def get_paths(self) -> GroupedDataPaths:
        grouper = GroupedDataPaths(grouping_attribute="value")
        for result in self.results:
            grouper.add_data_path(
                DataPath(  # type: ignore[call-arg]
                    branch=str(result.get("value_relationship").get("branch")),
                    path_type=PathType.ATTRIBUTE,
                    node_id=str(result.get("n.uuid")),
                    field_name=self.attribute_schema.name,
                    kind=self.node_schema.kind,
                    value=result.get("av.value"),
                )
            )

        return grouper


class AttributeRegexChecker(ConstraintCheckerInterface):
    query_classes = [AttributeRegexUpdateValidatorQuery]

    def __init__(self, db: InfrahubDatabase, branch: Optional[Branch]):
        self.db = db
        self.branch = branch

    @property
    def name(self) -> str:
        return "attribute.regex.update"

    def supports(self, message: SchemaValidatorPath) -> bool:
        return message.constraint_name == "attribute.regex.update"

    async def check(self, message: SchemaValidatorPath) -> List[GroupedDataPaths]:
        grouped_data_paths_list = []
        for query_class in self.query_classes:
            # TODO add exception handling
            query = await query_class.init(
                db=self.db, branch=self.branch, node_schema=message.node_schema, schema_path=message.schema_path
            )
            await query.execute(db=self.db)
            grouped_data_paths_list.append(await query.get_paths())
        return grouped_data_paths_list
