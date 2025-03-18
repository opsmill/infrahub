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


class AttributeLengthUpdateValidatorQuery(AttributeSchemaValidatorQuery):
    name: str = "attribute_constraints_length_validator"

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["attr_name"] = self.attribute_schema.name
        self.params["min_length"] = self.attribute_schema.min_length
        self.params["max_length"] = self.attribute_schema.max_length

        query = """
        MATCH (n:%(node_kind)s)
        CALL {
            WITH n
            MATCH path = (root:Root)<-[rr:IS_PART_OF]-(n)-[ra:HAS_ATTRIBUTE]-(:Attribute { name: $attr_name } )-[rv:HAS_VALUE]-(av:AttributeValue)
            WHERE all(
                r in relationships(path)
                WHERE %(branch_filter)s
            )
            RETURN path as full_path, n as node, rv as value_relationship, av.value as attribute_value
            ORDER BY rv.branch_level DESC, ra.branch_level DESC, rr.branch_level DESC, rv.from DESC, ra.from DESC, rr.from DESC
            LIMIT 1
        }
        WITH full_path, node, attribute_value, value_relationship
        WITH full_path, node, attribute_value, value_relationship
        WHERE all(r in relationships(full_path) WHERE r.status = "active")
        AND (
            (toInteger($min_length) IS NOT NULL AND size(attribute_value) < toInteger($min_length))
            OR (toInteger($max_length) IS NOT NULL AND size(attribute_value) > toInteger($max_length))
        )
        """ % {"branch_filter": branch_filter, "node_kind": self.node_schema.kind}

        self.add_to_query(query)
        self.return_labels = ["node.uuid", "value_relationship", "attribute_value"]

    async def get_paths(self) -> GroupedDataPaths:
        grouped_data_paths = GroupedDataPaths()
        for result in self.results:
            grouped_data_paths.add_data_path(
                DataPath(
                    branch=str(result.get("value_relationship").get("branch")),
                    path_type=PathType.ATTRIBUTE,
                    node_id=str(result.get("node.uuid")),
                    field_name=self.attribute_schema.name,
                    kind=self.node_schema.kind,
                ),
            )

        return grouped_data_paths


class AttributeLengthChecker(ConstraintCheckerInterface):
    query_classes = [AttributeLengthUpdateValidatorQuery]

    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None):
        self.db = db
        self.branch = branch

    @property
    def name(self) -> str:
        return "attribute.length.update"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name in ("attribute.min_length.update", "attribute.max_length.update")

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        grouped_data_paths_list: list[GroupedDataPaths] = []
        if not request.schema_path.field_name:
            raise ValueError("field_name is not defined")
        attribute_schema = request.node_schema.get_attribute(name=request.schema_path.field_name)
        if attribute_schema.min_length is None and attribute_schema.max_length is True:
            return grouped_data_paths_list

        for query_class in self.query_classes:
            # TODO add exception handling
            query = await query_class.init(
                db=self.db, branch=self.branch, node_schema=request.node_schema, schema_path=request.schema_path
            )
            await query.execute(db=self.db)
            grouped_data_paths_list.append(await query.get_paths())
        return grouped_data_paths_list
