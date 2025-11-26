from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.attribute import ListAttribute
from infrahub.core.constants import NULL_VALUE, PathType
from infrahub.core.path import DataPath, GroupedDataPaths
from infrahub.core.validators.enum import ConstraintIdentifier
from infrahub.exceptions import ValidationError
from infrahub.types import get_attribute_type

from ..interface import ConstraintCheckerInterface
from ..shared import AttributeSchemaValidatorQuery

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from ..model import SchemaConstraintValidatorRequest


class AttributeRegexUpdateValidatorQuery(AttributeSchemaValidatorQuery):
    name: str = "attribute_constraints_regex_validator"

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["attr_name"] = self.attribute_schema.name
        self.params["attr_value_regex"] = self.attribute_schema.get_regex()
        self.params["null_value"] = NULL_VALUE

        # For List attributes, we cannot validate regex in Cypher against the serialized JSON string
        # Instead, fetch all values and validate in Python after deserialization
        infrahub_data_type = get_attribute_type(self.attribute_schema.kind)
        infrahub_attribute_class = infrahub_data_type.get_infrahub_class()
        is_list_attribute = issubclass(infrahub_attribute_class, ListAttribute)

        if is_list_attribute:
            # Fetch all List attribute values, validate in get_paths()
            query = """
            MATCH p = (n:%(node_kind)s)
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
            AND attribute_value IS NOT NULL
            AND attribute_value <> $null_value
            """ % {"branch_filter": branch_filter, "node_kind": self.node_schema.kind}
        else:
            # For non-List attributes, use Cypher regex matching as before
            query = """
            MATCH p = (n:%(node_kind)s)
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
            AND attribute_value <> $null_value
            AND NOT attribute_value =~ $attr_value_regex
            """ % {"branch_filter": branch_filter, "node_kind": self.node_schema.kind}

        self.add_to_query(query)
        self.return_labels = ["node.uuid", "attribute_value", "value_relationship"]

    async def get_paths(self) -> GroupedDataPaths:
        grouped_data_paths = GroupedDataPaths()
        infrahub_data_type = get_attribute_type(self.attribute_schema.kind)
        infrahub_attribute_class = infrahub_data_type.get_infrahub_class()

        for result in self.results:
            value = result.get("attribute_value")

            # For List attributes, deserialize and validate each item
            if issubclass(infrahub_attribute_class, ListAttribute) and isinstance(value, str):
                try:
                    deserialized_value = infrahub_attribute_class.deserialize_from_string(value)
                    # Validate using the attribute's validate_content method
                    infrahub_attribute_class.validate_content(
                        value=deserialized_value, name=self.attribute_schema.name, schema=self.attribute_schema
                    )
                    # If validation passes, skip adding to grouped_data_paths (no violation)
                    continue
                except ValidationError:
                    # Validation failed, add to paths as a violation
                    pass

            # For non-List attributes or List attributes that failed validation
            value_str = str(value)
            grouped_data_paths.add_data_path(
                DataPath(
                    branch=str(result.get("value_relationship").get("branch")),
                    path_type=PathType.ATTRIBUTE,
                    node_id=str(result.get("node.uuid")),
                    field_name=self.attribute_schema.name,
                    kind=self.node_schema.kind,
                    value=value_str,
                ),
                grouping_key=value_str,
            )

        return grouped_data_paths


class AttributeRegexChecker(ConstraintCheckerInterface):
    query_classes = [AttributeRegexUpdateValidatorQuery]

    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None) -> None:
        self.db = db
        self.branch = branch

    @property
    def name(self) -> str:
        return "attribute.regex.update"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name in (self.name, ConstraintIdentifier.ATTRIBUTE_PARAMETERS_REGEX_UPDATE.value)

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        grouped_data_paths_list: list[GroupedDataPaths] = []
        if not request.schema_path.field_name:
            raise ValueError("field_name is not defined")
        attribute_schema = request.node_schema.get_attribute(name=request.schema_path.field_name)
        if not attribute_schema.get_regex():
            return grouped_data_paths_list

        for query_class in self.query_classes:
            # TODO add exception handling
            query = await query_class.init(
                db=self.db, branch=self.branch, node_schema=request.node_schema, schema_path=request.schema_path
            )
            await query.execute(db=self.db)
            grouped_data_paths_list.append(await query.get_paths())
        return grouped_data_paths_list
