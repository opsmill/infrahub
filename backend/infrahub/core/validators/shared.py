from __future__ import annotations

from typing import TYPE_CHECKING, List, Sequence, Union

from pydantic import BaseModel, ConfigDict, Field

from infrahub.core import registry
from infrahub.core.path import DataPath, SchemaPath  # noqa: TCH001
from infrahub.core.query import Query, QueryType
from infrahub.core.schema import AttributeSchema, GenericSchema, NodeSchema, RelationshipSchema  # noqa: TCH001

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class SchemaViolation(BaseModel):
    node_id: str
    node_kind: str
    display_label: str
    full_display_label: str
    message: str = ""


class SchemaValidatorQuery(Query):
    type: QueryType = QueryType.READ

    async def get_paths(self) -> List[DataPath]:
        raise NotImplementedError


class SchemaValidator(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str = Field(..., description="Name of the validator")
    queries: Sequence[type[SchemaValidatorQuery]] = Field(
        ..., description="List of queries to execute for this migration"
    )
    node_schema: Union[NodeSchema, GenericSchema]
    schema_path: SchemaPath

    async def run_validate(self, db: InfrahubDatabase, branch: Branch) -> List[SchemaViolation]:
        raw_paths: List[List[DataPath]] = []

        for migration_query in self.queries:
            # TODO add exception handling
            query = await migration_query.init(db=db, branch=branch, validator=self)
            await query.execute(db=db)
            raw_paths.append(await query.get_paths())

        ids = [path.node_id for paths in raw_paths for path in paths]
        fields = {"display_label": None, self.schema_path.field_name: None}
        nodes = await registry.manager.get_many(db=db, ids=ids, branch=branch, fields=fields)

        violations = []
        for paths in raw_paths:
            for path in paths:
                node_display_label = await nodes[path.node_id].render_display_label()
                if self.node_schema.display_labels:
                    display_label = f"Node {node_display_label} ({nodes[path.node_id].get_kind()}: {path.node_id})"
                else:
                    display_label = f"Node {node_display_label}"
                violation = SchemaViolation(
                    node_id=path.node_id,
                    node_kind=nodes[path.node_id].get_kind(),
                    display_label=node_display_label,
                    full_display_label=display_label,
                )
                # the error message is rendered in the SchemaValidator
                # to allow each migration to (re)define its own format
                violation.message = await self.render_error_message(violation=violation, data_path=path)
                violations.append(violation)

        return violations

    async def render_error_message(self, violation: SchemaViolation, data_path: DataPath) -> str:  # pylint: disable=unused-argument
        return f"{violation.full_display_label} is not compatible with the constraint {self.name!r} at {self.schema_path.get_path()!r}"


class AttributeSchemaValidator(SchemaValidator):
    @property
    def attribute_schema(self) -> AttributeSchema:
        return self.node_schema.get_attribute(name=self.schema_path.field_name)


class RelationshipSchemaValidator(SchemaValidator):
    @property
    def relationship_schema(self) -> RelationshipSchema:
        return self.node_schema.get_relationship(name=self.schema_path.field_name)
