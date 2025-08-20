from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import PathType
from infrahub.core.path import DataPath, GroupedDataPaths

from ..interface import ConstraintCheckerInterface
from ..shared import AttributeSchemaValidatorQuery

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from ..model import SchemaConstraintValidatorRequest


class AttributeUniqueUpdateValidatorQuery(AttributeSchemaValidatorQuery):
    name: str = "attribute_constraints_unique_validator"

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string(), is_isolated=False)
        self.params.update(branch_params)

        self.params["node_kind"] = self.node_schema.kind
        self.params["attr_name"] = self.attribute_schema.name

        from_times = db.render_list_comprehension(items="relationships(potential_path)", item_name="from")

        # ruff: noqa: E501
        query = """
        MATCH (potential_node:Node)
        WHERE $node_kind IN LABELS(potential_node)
        CALL (potential_node) {
            MATCH potential_path = (potential_node)-[:HAS_ATTRIBUTE]-(:Attribute { name: $attr_name })-[potential_value_relationship:HAS_VALUE]-(potential_value:AttributeValue)
            WHERE all(r IN relationships(potential_path) WHERE (%(branch_filter)s))
            WITH
                potential_value,
                potential_value_relationship,
                potential_path,
                reduce(br_lvl = 0, r in relationships(potential_path) | br_lvl + r.branch_level) AS branch_level,
                %(from_times)s AS from_times
            RETURN potential_node as node, potential_value as attribute_value, potential_path as path, potential_value_relationship as value_relationship
            ORDER BY branch_level DESC, from_times[-1] DESC, from_times[-2] DESC
            LIMIT 1
        }
        WITH node, attribute_value, path, value_relationship
        WHERE all(r IN relationships(path) WHERE (r.status = "active"))
        WITH
            collect([node, value_relationship]) as nodes_and_value_relationships,
            count(*) as node_count,
            attribute_value
        ORDER BY attribute_value.value
        UNWIND nodes_and_value_relationships as node_and_value_relationship
        """ % {"branch_filter": branch_filter, "from_times": from_times}

        self.add_to_query(query)
        self.return_labels = [
            "node_count",
            "attribute_value.value as value",
            "node_and_value_relationship[0] as node",
            "node_and_value_relationship[1] as value_relationship",
        ]

    async def get_paths(self) -> GroupedDataPaths:
        grouped_data_paths = GroupedDataPaths()
        for result in self.results:
            try:
                if int(result.get("node_count")) <= 1:  # type: ignore
                    continue
            except (ValueError, TypeError):
                continue
            value = str(result.get("value"))
            grouped_data_paths.add_data_path(
                DataPath(
                    path_type=PathType.ATTRIBUTE,
                    branch=str(result.get("value_relationship").get("branch")),
                    node_id=str(result.get("node").get("uuid")),
                    field_name=self.attribute_schema.name,
                    kind=self.node_schema.kind,
                    value=value,
                ),
                grouping_key=value,
            )

        return grouped_data_paths


class AttributeUniquenessChecker(ConstraintCheckerInterface):
    query_classes = [AttributeUniqueUpdateValidatorQuery]

    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None) -> None:
        self.db = db
        self.branch = branch

    @property
    def name(self) -> str:
        return "attribute.unique.update"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name == self.name

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        grouped_data_paths_list = []
        if not request.schema_path.field_name:
            raise ValueError("field_name is not defined")
        if request.node_schema.namespace == "Schema":
            # We don't need to run uniqueness constraints for attributes within the Schema nodes
            return []

        attribute_schema = request.node_schema.get_attribute(name=request.schema_path.field_name)
        if attribute_schema.unique is False:
            return []

        for query_class in self.query_classes:
            # TODO add exception handling
            query = await query_class.init(
                db=self.db, branch=self.branch, node_schema=request.node_schema, schema_path=request.schema_path
            )
            await query.execute(db=self.db)
            grouped_data_paths_list.append(await query.get_paths())
        return grouped_data_paths_list
