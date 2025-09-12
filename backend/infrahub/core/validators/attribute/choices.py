from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from infrahub.core.constants import NULL_VALUE, PathType
from infrahub.core.path import DataPath, GroupedDataPaths
from infrahub.core.schema.generic_schema import GenericSchema

from ..interface import ConstraintCheckerInterface
from ..shared import AttributeSchemaValidatorQuery

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from ..model import SchemaConstraintValidatorRequest


class AttributeChoicesUpdateValidatorQuery(AttributeSchemaValidatorQuery):
    name: str = "attribute_constraints_choices_validator"

    def __init__(
        self,
        excluded_kinds: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self.excluded_kinds: list[str] = excluded_kinds or []
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        if self.attribute_schema.choices is None:
            return

        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["attr_name"] = self.attribute_schema.name
        self.params["allowed_values"] = [choice.name for choice in self.attribute_schema.choices]
        self.params["null_value"] = NULL_VALUE
        self.params["excluded_kinds"] = self.excluded_kinds

        query = """
        MATCH (n:%(node_kind)s)
        WHERE size($excluded_kinds) = 0 OR NOT n.kind IN $excluded_kinds
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
        AND NOT (attribute_value IN $allowed_values)
        """ % {"branch_filter": branch_filter, "node_kind": self.node_schema.kind}

        self.add_to_query(query)
        self.return_labels = ["node.uuid", "attribute_value", "value_relationship"]

    async def get_paths(self) -> GroupedDataPaths:
        grouped_data_paths = GroupedDataPaths()
        for result in self.results:
            value = str(result.get("attribute_value"))
            grouped_data_paths.add_data_path(
                DataPath(
                    branch=str(result.get("value_relationship").get("branch")),
                    path_type=PathType.ATTRIBUTE,
                    node_id=str(result.get("node.uuid")),
                    field_name=self.attribute_schema.name,
                    kind=self.node_schema.kind,
                    value=value,
                ),
                grouping_key=value,
            )

        return grouped_data_paths


class AttributeChoicesChecker(ConstraintCheckerInterface):
    query_classes = [AttributeChoicesUpdateValidatorQuery]

    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None):
        self.db = db
        self.branch = branch

    @property
    def name(self) -> str:
        return "attribute.choices.update"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name == self.name

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        grouped_data_paths_list: list[GroupedDataPaths] = []
        if not request.schema_path.field_name:
            raise ValueError("field_name is not defined")
        attribute_schema = request.node_schema.get_attribute(name=request.schema_path.field_name)
        if attribute_schema.choices is None:
            return grouped_data_paths_list

        # skip inheriting schemas that override the attribute being checked
        excluded_kinds: list[str] = []
        if request.node_schema.is_generic_schema:
            request.node_schema = cast(GenericSchema, request.node_schema)
            for inheriting_kind in request.node_schema.used_by:
                inheriting_schema = request.schema_branch.get_node(name=inheriting_kind, duplicate=False)
                inheriting_schema_attribute = inheriting_schema.get_attribute(name=request.schema_path.field_name)
                if not inheriting_schema_attribute.inherited:
                    excluded_kinds.append(inheriting_kind)

        for query_class in self.query_classes:
            # TODO add exception handling
            query = await query_class.init(
                db=self.db,
                branch=self.branch,
                node_schema=request.node_schema,
                schema_path=request.schema_path,
                excluded_kinds=excluded_kinds,
            )
            await query.execute(db=self.db)
            grouped_data_paths_list.append(await query.get_paths())
        return grouped_data_paths_list
