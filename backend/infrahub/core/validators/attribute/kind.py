from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub.core.constants import NULL_VALUE, PathType
from infrahub.core.path import DataPath, GroupedDataPaths
from infrahub.exceptions import ValidationError
from infrahub.types import get_attribute_type

from ..interface import ConstraintCheckerInterface
from ..shared import AttributeSchemaValidatorQuery

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from ..model import SchemaConstraintValidatorRequest


@dataclass
class NodeAttributeValue:
    node_id: str
    attribute_value: Any
    branch_name: str


class AttributeKindUpdateValidatorQuery(AttributeSchemaValidatorQuery):
    name: str = "attribute_constraints_kind_validator"

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["attr_name"] = self.attribute_schema.name
        self.params["null_value"] = NULL_VALUE

        query = """
        MATCH p = (n:%(node_kind)s)
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
        AND attribute_value IS NOT NULL
        AND attribute_value <> $null_value
        """ % {"branch_filter": branch_filter, "node_kind": self.node_schema.kind}

        self.add_to_query(query)
        self.return_labels = ["node.uuid", "attribute_value", "value_relationship.branch as value_branch"]

    async def get_paths(self) -> GroupedDataPaths:
        grouped_data_paths = GroupedDataPaths()
        infrahub_data_type = get_attribute_type(self.attribute_schema.kind)
        infrahub_attribute_class = infrahub_data_type.get_infrahub_class()
        for result in self.get_results():
            value = result.get("attribute_value")
            if value in (None, NULL_VALUE):
                continue
            try:
                infrahub_attribute_class.validate_format(
                    value=result.get("attribute_value"), name=self.attribute_schema.name, schema=self.attribute_schema
                )
            except ValidationError:
                grouped_data_paths.add_data_path(
                    DataPath(
                        branch=str(result.get("value_branch")),
                        path_type=PathType.ATTRIBUTE,
                        node_id=str(result.get("node.uuid")),
                        field_name=self.attribute_schema.name,
                        kind=self.node_schema.kind,
                        value=value,
                    )
                )
        return grouped_data_paths


class AttributeKindChecker(ConstraintCheckerInterface):
    query_classes = [AttributeKindUpdateValidatorQuery]

    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None):
        self.db = db
        self.branch = branch

    @property
    def name(self) -> str:
        return "attribute.kind.update"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name == self.name

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        grouped_data_paths_list: list[GroupedDataPaths] = []
        for query_class in self.query_classes:
            # TODO add exception handling
            query = await query_class.init(
                db=self.db, branch=self.branch, node_schema=request.node_schema, schema_path=request.schema_path
            )

            await query.execute(db=self.db)
            grouped_data_paths_list.append(await query.get_paths())
        return grouped_data_paths_list
