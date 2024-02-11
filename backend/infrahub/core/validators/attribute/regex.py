from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Sequence

from infrahub.core.constants import PathType
from infrahub.core.path import DataPath

from ..shared import AttributeSchemaValidator, SchemaValidatorQuery

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


class AttributeRegexUpdateValidatorQuery(SchemaValidatorQuery):
    name: str = "attribute_constraints_regex_validator"

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

    async def get_paths(self) -> List[DataPath]:
        paths = []
        for result in self.results:
            paths.append(
                DataPath(  # type: ignore[call-arg]
                    path_type=PathType.ATTRIBUTE,
                    node_id=str(result.get("n.uuid")),
                    field_name=self.validator.attribute_schema.name,
                    kind=self.validator.node_schema.kind,
                    value=result.get("av.value"),
                )
            )

        return paths


class AttributeRegexUpdateValidator(AttributeSchemaValidator):
    name: str = "attribute.regex.update"
    queries: Sequence[type[SchemaValidatorQuery]] = [AttributeRegexUpdateValidatorQuery]
