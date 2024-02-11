from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Union

from infrahub.core import registry
from infrahub.core.constants import PathResourceType, PathType
from infrahub.core.path import DataPath
from infrahub.core.query import Query, QueryType
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema  # noqa: TCH001

from ..shared import SchemaValidator, SchemaViolation

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class AttributeRegexUpdateValidatorQuery(Query):
    name = "attribute_constraints_regex_validator"
    type: QueryType = QueryType.WRITE

    def __init__(
        self,
        *args: Any,
        validator: AttributeRegexUpdateValidator,
        **kwargs: Any,
    ):
        self.validator = validator

        super().__init__(*args, **kwargs)

    async def query_init(self, db: InfrahubDatabase, *args: Any, **kwargs: Dict[str, Any]) -> None:
        branch_filter, branch_params = self.branch.get_query_filter_path(at=self.at.to_string())
        self.params.update(branch_params)

        self.params["node_kind"] = self.validator.node_schema.kind
        self.params["attr_name"] = self.validator.attribute_schema.name
        self.params["attr_value_regex"] = self.validator.attribute_schema.regex

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
        WHERE NOT av.value =~ $attr_value_regex AND all(r IN relationships(path) WHERE (%(branch_filter)s))
        """ % {"branch_filter": branch_filter}

        self.add_to_query(query)
        self.return_labels = ["n.uuid", "av.value"]

    def get_paths(self) -> List[DataPath]:
        paths = []
        for result in self.results:
            paths.append(
                DataPath(  # type: ignore[call-arg]
                    resource_type=PathResourceType.DATA,
                    path_type=PathType.ATTRIBUTE,
                    node_id=str(result.get("n.uuid")),
                    field_name=self.validator.attribute_schema.name,
                    kind=self.validator.node_schema.kind,
                    value=result.get("av.value"),
                )
            )

        return paths


class AttributeRegexUpdateValidator(SchemaValidator):
    name: str = "attribute.regex.update"

    node_schema: Union[NodeSchema, GenericSchema]
    attribute_name: str

    @property
    def attribute_schema(self) -> AttributeSchema:
        return self.node_schema.get_attribute(name=self.attribute_name)

    async def run_validate(self, db: InfrahubDatabase, branch: Branch) -> List[SchemaViolation]:
        query = await AttributeRegexUpdateValidatorQuery.init(db=db, branch=branch, validator=self)
        await query.execute(db=db)
        paths = query.get_paths()

        ids = [path.node_id for path in paths]
        fields = {"display_label": None, self.attribute_name: None}
        nodes = await registry.manager.get_many(db=db, ids=ids, branch=branch, fields=fields)

        return [
            SchemaViolation(node_id=node.id, node_kind=node.get_kind(), display_label=await node.render_display_label())
            for node in nodes.values()
        ]
