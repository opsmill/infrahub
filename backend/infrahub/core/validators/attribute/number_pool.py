from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import PathType
from infrahub.core.path import DataPath, GroupedDataPaths
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.validators.enum import ConstraintIdentifier

from ..interface import ConstraintCheckerInterface
from ..shared import AttributeSchemaValidatorQuery

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from ..model import SchemaConstraintValidatorRequest


class AttributeNumberPoolUpdateValidatorQuery(AttributeSchemaValidatorQuery):
    name: str = "attribute_constraints_numberpool_validator"

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        if not isinstance(self.attribute_schema.parameters, NumberPoolParameters):
            raise ValueError("attribute parameters are not a NumberPoolParameters")

        self.params["attr_name"] = self.attribute_schema.name
        self.params["start_range"] = self.attribute_schema.parameters.start_range
        self.params["end_range"] = self.attribute_schema.parameters.end_range

        query = """
        MATCH (n:%(node_kind)s)
        CALL (n) {
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
        WHERE all(r in relationships(full_path) WHERE r.status = "active")
        AND (
            (toInteger($start_range) IS NOT NULL AND attribute_value < toInteger($start_range))
            OR (toInteger($end_range) IS NOT NULL AND attribute_value > toInteger($end_range))
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
                    value=result.get("attribute_value"),
                ),
            )

        return grouped_data_paths


class AttributeNumberPoolChecker(ConstraintCheckerInterface):
    query_classes = [AttributeNumberPoolUpdateValidatorQuery]

    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None):
        self.db = db
        self.branch = branch

    @property
    def name(self) -> str:
        return "attribute.number.update"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name in (
            ConstraintIdentifier.ATTRIBUTE_PARAMETERS_START_RANGE_UPDATE.value,
            ConstraintIdentifier.ATTRIBUTE_PARAMETERS_END_RANGE_UPDATE.value,
        )

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        grouped_data_paths_list: list[GroupedDataPaths] = []
        if not request.schema_path.field_name:
            raise ValueError("field_name is not defined")
        attribute_schema = request.node_schema.get_attribute(name=request.schema_path.field_name)
        if not isinstance(attribute_schema.parameters, NumberPoolParameters):
            raise ValueError("attribute parameters are not a NumberPoolParameters")

        for query_class in self.query_classes:
            # TODO add exception handling
            query = await query_class.init(
                db=self.db, branch=self.branch, node_schema=request.node_schema, schema_path=request.schema_path
            )
            await query.execute(db=self.db)
            grouped_data_paths_list.append(await query.get_paths())
        return grouped_data_paths_list
