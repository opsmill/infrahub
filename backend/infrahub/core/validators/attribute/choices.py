from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from infrahub.core.constants import PathType
from infrahub.core.path import DataPath, GroupedDataPaths

from ..interface import ConstraintCheckerInterface
from ..shared import AttributeSchemaValidatorQuery

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from ..model import SchemaConstraintValidatorRequest


class AttributeChoicesUpdateValidatorQuery(AttributeSchemaValidatorQuery):
    name: str = "attribute_constraints_choices_validator"

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Dict[str, Any]) -> None:
        if self.attribute_schema.choices is None:
            return

        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["node_kind"] = self.node_schema.kind
        self.params["attr_name"] = self.attribute_schema.name
        self.params["allowed_values"] = [choice.name for choice in self.attribute_schema.choices]

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
        WHERE all(r IN relationships(path) WHERE (%(branch_filter)s))
        WITH path, n, av
        WITH path, n, av
        WHERE av.value IS NOT NULL AND av.value != "NULL" AND NOT (av.value IN $allowed_values)
        """ % {"branch_filter": branch_filter}

        self.add_to_query(query)
        self.return_labels = ["n.uuid", "av.value", "relationships(path)[-1] as value_relationship"]

    async def get_paths(self) -> GroupedDataPaths:
        grouped_data_paths = GroupedDataPaths()
        for result in self.results:
            value = str(result.get("av.value"))
            grouped_data_paths.add_data_path(
                DataPath(
                    branch=str(result.get("value_relationship").get("branch")),
                    path_type=PathType.ATTRIBUTE,
                    node_id=str(result.get("n.uuid")),
                    field_name=self.attribute_schema.name,
                    kind=self.node_schema.kind,
                    value=value,
                ),
                grouping_key=value,
            )

        return grouped_data_paths


class AttributeChoicesChecker(ConstraintCheckerInterface):
    query_classes = [AttributeChoicesUpdateValidatorQuery]

    def __init__(self, db: InfrahubDatabase, branch: Optional[Branch]):
        self.db = db
        self.branch = branch

    @property
    def name(self) -> str:
        return "attribute.choices.update"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name == "attribute.choices.update"

    async def check(self, request: SchemaConstraintValidatorRequest) -> List[GroupedDataPaths]:
        grouped_data_paths_list: List[GroupedDataPaths] = []
        for query_class in self.query_classes:
            # TODO add exception handling
            query = await query_class.init(
                db=self.db, branch=self.branch, node_schema=request.node_schema, schema_path=request.schema_path
            )
            await query.execute(db=self.db)
            grouped_data_paths_list.append(await query.get_paths())
        return grouped_data_paths_list
