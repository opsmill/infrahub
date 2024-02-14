from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Sequence

from infrahub.core.constants import PathType
from infrahub.core.path import DataPath, GroupedDataPaths

from ..shared import AttributeSchemaValidator, AttributeSchemaValidatorQuery, SchemaValidatorQuery, SchemaViolation

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class AttributeUniqueUpdateValidatorQuery(AttributeSchemaValidatorQuery):
    name: str = "attribute_constraints_unique_validator"

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Dict[str, Any]) -> None:
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["node_kind"] = self.node_schema.kind
        self.params["attr_name"] = self.attribute_schema.name

        from_times = db.render_list_comprehension(items="relationships(potential_path)", item_name="from")

        query = """
        MATCH (potential_node:Node)
        WHERE $node_kind IN LABELS(potential_node)
        CALL {
            WITH potential_node
            MATCH potential_path = (potential_node)-[:HAS_ATTRIBUTE]-(:Attribute { name: $attr_name })-[:HAS_VALUE]-(potential_value:AttributeValue)
            WHERE all(r IN relationships(potential_path) WHERE (%(branch_filter)s))
            WITH
                potential_value,
                potential_path,
                reduce(br_lvl = 0, r in relationships(potential_path) | br_lvl + r.branch_level) AS branch_level,
                %(from_times)s AS from_times
            RETURN potential_node as node, potential_value as attribute_value, potential_path as path
            ORDER BY branch_level DESC, from_times[-1] DESC, from_times[-2] DESC
            LIMIT 1
        }
        WITH node, attribute_value, path
        WHERE all(r IN relationships(path) WHERE (r.status = "active"))
        WITH count(*) as node_count, attribute_value, node, path
        ORDER BY attribute_value.value
        """ % {"branch_filter": branch_filter, "from_times": from_times}

        self.add_to_query(query)
        self.return_labels = [
            "node_count",
            "attribute_value.value as value",
            "node",
            "relationships(path)[-1] as value_relationship",
        ]

    async def get_paths(self) -> GroupedDataPaths:
        grouper = GroupedDataPaths(grouping_attribute="value")
        for result in self.results:
            grouper.add_data_path(
                DataPath(  # type: ignore[call-arg]
                    path_type=PathType.ATTRIBUTE,
                    branch=str(result.get("value_relationship").get("branch")),
                    node_id=str(result.get("node").get("uuid")),
                    field_name=self.attribute_schema.name,
                    kind=self.node_schema.kind,
                    value=result.get("value"),
                )
            )

        return grouper


class AttributeUniqueUpdateValidator(AttributeSchemaValidator):
    name: str = "attribute.unique.update"
    queries: Sequence[type[SchemaValidatorQuery]] = [AttributeUniqueUpdateValidatorQuery]

    async def run_validate(self, db: InfrahubDatabase, branch: Branch) -> List[SchemaViolation]:
        # if the new attribute schema is NOT unique
        # there is no need to validate the data at all
        if self.attribute_schema.unique is False:
            return []
        return await super().run_validate(db=db, branch=branch)
