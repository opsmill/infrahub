from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Self

from infrahub_sdk.graphql import Query
from pydantic import BaseModel, Field

from infrahub.core.constants import RelationshipCardinality
from infrahub.core.registry import registry
from infrahub.core.schema import NodeSchema  # noqa: TC001
from infrahub.events import NodeUpdatedEvent
from infrahub.trigger.constants import NAME_SEPARATOR
from infrahub.trigger.models import (
    EventTrigger,
    ExecuteWorkflow,
    TriggerBranchDefinition,
    TriggerType,
)
from infrahub.workflows.catalogue import DISPLAY_LABELS_PROCESS_JINJA2

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch_display import DisplayLabels, RelationshipTriggers


@dataclass
class AttributeTarget:
    hash: str
    fields: set[str]


class DisplayLabelTriggerDefinition(TriggerBranchDefinition):
    type: TriggerType = TriggerType.DISPLAY_LABEL_JINJA2
    template_hash: str
    target_kind: str | None = Field(default=None)

    def get_description(self) -> str:
        return f"{super().get_description()} | hash:{self.template_hash}"

    @classmethod
    def from_schema_display_labels(
        cls,
        branch: str,
        display_labels: DisplayLabels,
        branches_out_of_scope: list[str] | None = None,
    ) -> list[DisplayLabelTriggerDefinition]:
        """
        This function is used to create a trigger definition for a display labels of type Jinja2.
        """

        definitions: list[DisplayLabelTriggerDefinition] = []

        for node_kind, template_label in display_labels.get_template_nodes().items():
            definitions.append(
                cls.new(
                    branch=branch,
                    node_kind=node_kind,
                    target_kind=node_kind,
                    fields=[
                        "_trigger_placeholder"
                    ],  # Triggers for the nodes themselves are only used to determine if all nodes should be regenerated
                    template_hash=template_label.get_hash(),
                    branches_out_of_scope=branches_out_of_scope,
                )
            )

        for related_kind, relationship_trigger in display_labels.get_related_trigger_nodes().items():
            definitions.extend(
                cls.from_related_node(
                    branch=branch,
                    related_kind=related_kind,
                    relationship_trigger=relationship_trigger,
                    display_labels=display_labels,
                    branches_out_of_scope=branches_out_of_scope,
                )
            )

        return definitions

    @classmethod
    def from_related_node(
        cls,
        branch: str,
        related_kind: str,
        relationship_trigger: RelationshipTriggers,
        display_labels: DisplayLabels,
        branches_out_of_scope: list[str] | None = None,
    ) -> list[DisplayLabelTriggerDefinition]:
        targets_by_attribute: dict[str, AttributeTarget] = {}
        definitions: list[DisplayLabelTriggerDefinition] = []
        for attribute, relationship_identifiers in relationship_trigger.attributes.items():
            for relationship_identifier in relationship_identifiers:
                actual_node = display_labels.get_template_node(kind=relationship_identifier.kind)
                if relationship_identifier.kind not in targets_by_attribute:
                    targets_by_attribute[relationship_identifier.kind] = AttributeTarget(
                        actual_node.get_hash(), fields=set()
                    )
                targets_by_attribute[relationship_identifier.kind].fields.add(attribute)

        for target_kind, attribute_target in targets_by_attribute.items():
            definitions.append(
                cls.new(
                    branch=branch,
                    node_kind=related_kind,
                    target_kind=target_kind,
                    fields=sorted(attribute_target.fields),
                    template_hash=attribute_target.hash,
                    branches_out_of_scope=branches_out_of_scope,
                )
            )

        return definitions

    @classmethod
    def new(
        cls,
        branch: str,
        node_kind: str,
        target_kind: str,
        template_hash: str,
        fields: list[str],
        branches_out_of_scope: list[str] | None = None,
    ) -> Self:
        event_trigger = EventTrigger()
        event_trigger.events.add(NodeUpdatedEvent.event_name)
        event_trigger.match = {"infrahub.node.kind": node_kind}
        if branches_out_of_scope:
            event_trigger.match["infrahub.branch.name"] = [f"!{branch}" for branch in branches_out_of_scope]
        elif not branches_out_of_scope and branch != registry.default_branch:
            event_trigger.match["infrahub.branch.name"] = branch

        event_trigger.match_related = {
            "prefect.resource.role": ["infrahub.node.attribute_update", "infrahub.node.relationship_update"],
            "infrahub.field.name": fields,
        }

        workflow = ExecuteWorkflow(
            workflow=DISPLAY_LABELS_PROCESS_JINJA2,
            parameters={
                "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                "node_kind": node_kind,
                "object_id": "{{ event.resource['infrahub.node.id'] }}",
                "target_kind": target_kind,
                "context": {
                    "__prefect_kind": "json",
                    "value": {
                        "__prefect_kind": "jinja",
                        "template": "{{ event.payload['context'] | tojson }}",
                    },
                },
            },
        )

        trigger_definition_target_kind = target_kind if target_kind == node_kind else None

        return cls(
            name=f"{target_kind}{NAME_SEPARATOR}by{NAME_SEPARATOR}{node_kind}",
            template_hash=template_hash,
            branch=branch,
            trigger=event_trigger,
            actions=[workflow],
            target_kind=trigger_definition_target_kind,
        )


class DisplayLabelJinja2GraphQLResponse(BaseModel):
    node_id: str
    display_label_value: str | None
    variables: dict[str, Any] = Field(default_factory=dict)


class DisplayLabelJinja2GraphQL(BaseModel):
    filter_key: str
    node_schema: NodeSchema = Field(..., description="The node kind where the computed attribute is defined")
    variables: list[str] = Field(..., description="The list of variable names used within the computed attribute")

    def render_graphql_query(self, filter_id: str) -> str:
        query_fields = self.query_fields
        query_fields["id"] = None
        query_fields["display_label"] = None
        query = Query(
            name="DisplayLabelFilter",
            query={
                self.node_schema.kind: {
                    "@filters": {self.filter_key: filter_id},
                    "edges": {"node": query_fields},
                }
            },
        )

        return query.render()

    @property
    def query_fields(self) -> dict[str, Any]:
        output: dict[str, Any] = {}
        for variable in self.variables:
            field_name, remainder = variable.split("__", maxsplit=1)
            if field_name in self.node_schema.attribute_names:
                output[field_name] = {remainder: None}
            elif field_name in self.node_schema.relationship_names:
                related_attribute, related_value = remainder.split("__", maxsplit=1)
                relationship = self.node_schema.get_relationship(name=field_name)
                if relationship.cardinality == RelationshipCardinality.ONE:
                    if field_name not in output:
                        output[field_name] = {"node": {}}
                    output[field_name]["node"][related_attribute] = {related_value: None}
        return output

    def parse_response(self, response: dict[str, Any]) -> list[DisplayLabelJinja2GraphQLResponse]:
        rendered_response: list[DisplayLabelJinja2GraphQLResponse] = []
        if kind_payload := response.get(self.node_schema.kind):
            edges = kind_payload.get("edges", [])
            for node in edges:
                if node_response := self.to_node_response(node_dict=node):
                    rendered_response.append(node_response)
        return rendered_response

    def to_node_response(self, node_dict: dict[str, Any]) -> DisplayLabelJinja2GraphQLResponse | None:
        if node := node_dict.get("node"):
            node_id = node.get("id")
        else:
            return None

        display_label = node.get("display_label")
        response = DisplayLabelJinja2GraphQLResponse(node_id=node_id, display_label_value=display_label)
        for variable in self.variables:
            field_name, remainder = variable.split("__", maxsplit=1)
            response.variables[variable] = None
            if field_content := node.get(field_name):
                if field_name in self.node_schema.attribute_names:
                    response.variables[variable] = field_content.get(remainder)
                elif field_name in self.node_schema.relationship_names:
                    relationship = self.node_schema.get_relationship(name=field_name)
                    if relationship.cardinality == RelationshipCardinality.ONE:
                        related_attribute, related_value = remainder.split("__", maxsplit=1)
                        node_content = field_content.get("node") or {}
                        related_attribute_content = node_content.get(related_attribute) or {}
                        response.variables[variable] = related_attribute_content.get(related_value)

        return response
