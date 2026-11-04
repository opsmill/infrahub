from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub.core import registry
from infrahub.core.constants import NULL_VALUE, PathType
from infrahub.core.path import DataPath, GroupedDataPaths
from infrahub.core.schema.attribute_parameters import NumberPoolParameters

from ..interface import ConstraintCheckerInterface
from ..shared import AttributeSchemaValidatorQuery

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

    from ..model import SchemaConstraintValidatorRequest


class NodeAttributeValueMissingValidatorQuery(AttributeSchemaValidatorQuery):
    """Find the active nodes of the kind that have no value for the attribute.

    The attribute is matched optionally because a node created before the attribute was added has no vertex for it.
    """

    name: str = "node_attribute_value_missing_validator"

    async def query_init(self, db: InfrahubDatabase, **kwargs: Any) -> None:  # noqa: ARG002
        branch_filter, branch_params = self.branch.get_query_filter_path(
            at=self.at.to_string(), is_isolated=self.is_isolated
        )
        self.params.update(branch_params)

        self.params["attr_name"] = self.attribute_schema.name
        self.params["null_value"] = NULL_VALUE

        query = """
        MATCH (n:%(node_kind)s)
        CALL (n) {
            MATCH path = (:Root)<-[rr:IS_PART_OF]-(n)
            WHERE all(
                r in relationships(path)
                WHERE %(branch_filter)s
            )
            RETURN rr.branch AS root_branch, rr.status AS root_status
            ORDER BY rr.branch_level DESC, rr.from DESC, rr.status ASC
            LIMIT 1
        }
        WITH n, root_branch, root_status
        WHERE root_status = "active"
        CALL (n) {
            OPTIONAL MATCH path = (n)-[ra:HAS_ATTRIBUTE]-(:Attribute { name: $attr_name })-[rv:HAS_VALUE]-(av:AttributeValue)
            WHERE all(
                r in relationships(path)
                WHERE %(branch_filter)s
            )
            RETURN ra.status AS attribute_status, rv.status AS value_status, av.value AS attribute_value
            ORDER BY rv.branch_level DESC, ra.branch_level DESC, rv.from DESC, ra.from DESC, rv.status ASC, ra.status ASC
            LIMIT 1
        }
        WITH n, root_branch, attribute_status, value_status, attribute_value
        WHERE attribute_status IS NULL
            OR attribute_status <> "active"
            OR value_status <> "active"
            OR attribute_value IS NULL
            OR attribute_value = $null_value
        """ % {"branch_filter": branch_filter, "node_kind": self.node_schema.kind}

        self.add_to_query(query)
        self.return_labels = ["n.uuid", "root_branch"]

    async def get_paths(self) -> GroupedDataPaths:
        grouped_data_paths = GroupedDataPaths()
        for result in self.results:
            grouped_data_paths.add_data_path(
                DataPath(
                    branch=str(result.get("root_branch")),
                    path_type=PathType.NODE,
                    node_id=str(result.get("n.uuid")),
                    kind=self.node_schema.kind,
                ),
            )

        return grouped_data_paths


class NodeAttributeAddChecker(ConstraintCheckerInterface):
    query_classes = [NodeAttributeValueMissingValidatorQuery]

    def __init__(self, db: InfrahubDatabase, branch: Branch | None = None) -> None:
        self.db = db
        self.branch = branch

    @property
    def name(self) -> str:
        return "node.attribute.add"

    def supports(self, request: SchemaConstraintValidatorRequest) -> bool:
        return request.constraint_name == self.name

    async def check(self, request: SchemaConstraintValidatorRequest) -> list[GroupedDataPaths]:
        grouped_data_paths_list: list[GroupedDataPaths] = []
        if not request.schema_path.field_name:
            raise ValueError("field_name is not defined")

        attribute_schema = request.node_schema.get_attribute(name=request.schema_path.field_name)
        if attribute_schema.optional is True or attribute_schema.default_value is not None:
            return grouped_data_paths_list

        # If the attribute is a NumberPool, we need to ensure that the pool is big enough for all existing nodes
        if attribute_schema.kind == "NumberPool" and isinstance(attribute_schema.parameters, NumberPoolParameters):
            # A scoped pool's limit applies to each division, which the migration enforces as it allocates.
            if attribute_schema.parameters.allocation_scope:
                return grouped_data_paths_list
            # The node count reads its view from the branch rather than from a parameter.
            count_branch = self.branch
            if count_branch is not None and not request.is_isolated:
                count_branch = count_branch.model_copy(update={"is_isolated": False})
            nbr_nodes = await registry.manager.count(db=self.db, branch=count_branch, schema=request.node_schema)
            pool_size = attribute_schema.parameters.get_pool_size()

            if pool_size < nbr_nodes:
                raise ValueError(
                    f"The size of the NumberPool is smaller than the number of existing nodes {pool_size} < {nbr_nodes}."
                )
            return grouped_data_paths_list

        for query_class in self.query_classes:
            # TODO add exception handling
            query = await query_class.init(
                db=self.db,
                branch=self.branch,
                node_schema=request.node_schema,
                schema_path=request.schema_path,
                is_isolated=request.is_isolated,
            )
            await query.execute(db=self.db)
            grouped_data_paths_list.append(await query.get_paths())
        return grouped_data_paths_list
