from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel, Field

from infrahub.exceptions import InitializationError

if TYPE_CHECKING:
    from graphql.language import FieldNode


class GraphQLDirective(BaseModel):
    kind: str
    name: GraphQLFieldName
    arguments: list[dict]


class GraphQLFieldName(BaseModel):
    kind: str
    value: str


class GraphQLSelection(BaseModel):
    kind: str
    directives: list[GraphQLDirective] = Field(default_factory=list)
    alias: Optional[Any] = None
    name: Optional[GraphQLFieldName] = Field(default=None)
    arguments: list[dict] = Field(default_factory=list)
    selection_set: Optional[GraphQLSelectionSet] = Field(default=None)
    type_condition: Optional[dict] = Field(default=None)

    @property
    def node_name(self) -> GraphQLFieldName:
        if not self.name:
            raise InitializationError("The selection is not initialized with a node name")
        return self.name

    @property
    def is_field_node(self) -> bool:
        return self.kind == "field"

    @property
    def is_inline_fragment_node(self) -> bool:
        return self.kind == "inline_fragment"


class GraphQLSelectionSet(BaseModel):
    kind: str
    selections: list[GraphQLSelection] = Field(default_factory=list)


def parse_fields(selection_set: Optional[GraphQLSelectionSet]) -> Optional[dict]:
    fields = {}
    if not selection_set:
        return None
    for selection in selection_set.selections:
        if selection.is_field_node:
            fields[selection.node_name.value] = parse_fields(selection.selection_set)
        elif selection.is_inline_fragment_node and selection.selection_set:
            for sub_node in selection.selection_set.selections:
                if sub_node.is_field_node:
                    fields[sub_node.node_name.value] = parse_fields(sub_node.selection_set)

    return fields


def extract_selection_set_fields(field_node: FieldNode) -> dict:
    if not field_node.selection_set:
        return {}
    selection_set = GraphQLSelectionSet(**field_node.selection_set.to_dict())
    return parse_fields(selection_set=selection_set) or {}
