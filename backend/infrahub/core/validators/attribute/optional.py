from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core.constants import NULL_VALUE, PathType
from infrahub.core.path import DataPath, GroupedDataPaths
from infrahub.core.schema.generic_schema import GenericSchema

from ..interface import ConstraintCheckerInterface
from ..shared import AttributeSchemaValidatorQuery

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from ..model import SchemaConstraintValidatorRequest


class AttributeOptionalUpdateValidatorQuery(AttributeSchemaValidatorQuery):
    name: str = "attribute_constraints_optional_validator"

    def __init__(self, excluded_kinds: list[str] | None = None, **kwargs: Any) -> None:
        self.excluded_kinds = excluded_kinds or []
        super().__init__(**kwargs)

    async def query_init(self, db: InfrahubDatabase, **kwargs: dict[str, Any]) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["attr_name"] = self.attribute_schema.name
        self.params["null_value"] = NULL_VALUE
        self.params["excluded_kinds"] = self.excluded_kinds

        query = """
        MATCH (n:%(node_kind)s)
        WHERE NONE(kind IN $excluded_kinds WHERE kind IN labels(n))
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
        AND (attribute_value IS NULL OR attribute_value = $null_value)
        """ % {"branch_filter": branch_filter, "node_kind": self.node_schema.kind}

        self.add_to_query(query)
        self.return_labels = ["node.uuid", "node.kind", "value_relationship"]

    async def get_paths(self) -> GroupedDataPaths:
        grouped_data_paths = GroupedDataPaths()
        for result in self.results:
            grouped_data_paths.add_data_path(
                DataPath(
                    branch=str(result.get("value_relationship").get("branch")),
                    path_type=PathType.ATTRIBUTE,
                    node_id=str(result.get("node.uuid")),
                    field_name=self.attribute_schema.name,
                    kind=str(result.get("node.kind")),
                ),
            )

        return grouped_data_paths


class AttributeOptionalChecker(ConstraintCheckerInterface):
    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None) -> None:
        self.db = db
        self.branch = branch

    @property
    def name(self) -> str:
        return "attribute.optional.update"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name == self.name

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        if not request.schema_path.field_name:
            raise ValueError("field_name is not defined")
        attribute_schema = request.node_schema.get_attribute(name=request.schema_path.field_name)
        if attribute_schema.optional is True:
            return []

        # For generic schemas, a single MATCH on the generic's kind label finds instances of all
        # inheriting node types. Exclude child nodes that locally override the attribute to optional.
        excluded_kinds: list[str] = []
        if isinstance(request.node_schema, GenericSchema):
            excluded_kinds = [
                node_kind
                for node_kind in request.node_schema.used_by
                if request.schema_branch.get_node(name=node_kind, duplicate=False)
                .get_attribute(name=request.schema_path.field_name)
                .optional
                is True
            ]

        query = await AttributeOptionalUpdateValidatorQuery.init(
            db=self.db,
            branch=self.branch,
            node_schema=request.node_schema,
            schema_path=request.schema_path,
            excluded_kinds=excluded_kinds,
        )
        await query.execute(db=self.db)
        return [await query.get_paths()]
