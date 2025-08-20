from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from infrahub_sdk.graphql import Query
from prefect.events.schemas.automations import Automation  # noqa: TC002
from pydantic import BaseModel, ConfigDict, Field, computed_field
from typing_extensions import Self

from infrahub.core import registry
from infrahub.core.constants import RelationshipCardinality
from infrahub.core.schema import AttributeSchema, NodeSchema  # noqa: TC001
from infrahub.core.schema.schema_branch_computed import (  # noqa: TC001
    ComputedAttributeTarget,
    ComputedAttributeTriggerNode,
    PythonDefinition,
)
from infrahub.events import NodeCreatedEvent, NodeUpdatedEvent
from infrahub.graphql.analyzer import InfrahubGraphQLQueryAnalyzer  # noqa: TC001
from infrahub.trigger.constants import NAME_SEPARATOR
from infrahub.trigger.models import (
    EventTrigger,
    ExecuteWorkflow,
    TriggerBranchDefinition,
    TriggerType,
)
from infrahub.workflows.catalogue import (
    COMPUTED_ATTRIBUTE_PROCESS_JINJA2,
    COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM,
    QUERY_COMPUTED_ATTRIBUTE_TRANSFORM_TARGETS,
)

if TYPE_CHECKING:
    from uuid import UUID

    from infrahub.git.models import RepositoryData


class ComputedAttributeAutomations(BaseModel):
    data: dict[str, dict[str, Automation]] = Field(default_factory=lambda: defaultdict(dict))  # type: ignore[arg-type]

    @classmethod
    def from_prefect(cls, automations: list[Automation], prefix: str = "") -> Self:
        obj = cls()
        for automation in automations:
            if not automation.name.startswith(prefix):
                continue

            name_split = automation.name.split(NAME_SEPARATOR)
            if len(name_split) != 3:
                continue

            scope = name_split[1]
            identifier = name_split[2]

            obj.data[identifier][scope] = automation

        return obj

    def get(self, identifier: str, scope: str) -> Automation:
        if identifier in self.data and scope in self.data[identifier]:
            return self.data[identifier][scope]
        raise KeyError(f"Unable to find an automation for {identifier} {scope}")

    def has(self, identifier: str, scope: str) -> bool:
        if identifier in self.data and scope in self.data[identifier]:
            return True
        return False

    @property
    def all_automation_ids(self) -> list[UUID]:
        automation_ids: list[UUID] = []
        for identifier in self.data.values():
            for automation in identifier.values():
                automation_ids.append(automation.id)
        return automation_ids


class PythonTransformComputedAttribute(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str
    repository_id: str
    repository_name: str
    repository_kind: str
    query_name: str
    query_analyzer: InfrahubGraphQLQueryAnalyzer
    computed_attribute: PythonDefinition
    default_schema: bool
    branch_name: str
    branch_commit: dict[str, str] = field(default_factory=dict)

    @computed_field
    def repository_commit(self) -> str:
        return self.branch_commit[self.branch_name]

    def populate_branch_commit(self, repository_data: RepositoryData | None = None) -> None:
        if repository_data:
            for branch, commit in repository_data.branches.items():
                self.branch_commit[branch] = commit

    def get_altered_branches(self) -> list[str]:
        if registry.default_branch in self.branch_commit:
            default_branch_commit = self.branch_commit[registry.default_branch]
            return [
                branch_name for branch_name, commit in self.branch_commit.items() if commit != default_branch_commit
            ]
        return list(self.branch_commit.keys())


@dataclass
class PythonTransformTarget:
    kind: str
    object_id: str


class ComputedAttrJinja2TriggerDefinition(TriggerBranchDefinition):
    type: TriggerType = TriggerType.COMPUTED_ATTR_JINJA2
    computed_attribute: ComputedAttributeTarget
    template_hash: str

    def get_description(self) -> str:
        return f"{super().get_description()} | hash:{self.template_hash}"

    @classmethod
    def from_computed_attribute(
        cls,
        branch: str,
        computed_attribute: ComputedAttributeTarget,
        trigger_node: ComputedAttributeTriggerNode,
        branches_out_of_scope: list[str] | None = None,
    ) -> Self:
        """
        This function is used to create a trigger definition for a computed attribute of type Jinja2.
        """
        event_trigger = EventTrigger()
        event_trigger.events.add(NodeUpdatedEvent.event_name)
        if computed_attribute.attribute.optional:
            # If the computed attribute not optional it means that Infrahub will have assigned the value during
            # the creation of the node so we don't need to match on node creation events as it would only add
            # extra work that doesn't accomplish anything. For this reason the filter should only match on the
            # node creation events if the attribute is optional.
            event_trigger.events.add(NodeCreatedEvent.event_name)

        if (
            computed_attribute.attribute.computed_attribute
            and computed_attribute.attribute.computed_attribute.jinja2_template is None
        ) or not computed_attribute.attribute.computed_attribute:
            raise ValueError("Jinja2 template is required for computed attribute")

        template_hash = computed_attribute.attribute.computed_attribute.get_hash()

        event_trigger.match = {"infrahub.node.kind": trigger_node.kind}
        if branches_out_of_scope:
            event_trigger.match["infrahub.branch.name"] = [f"!{branch}" for branch in branches_out_of_scope]
        elif not branches_out_of_scope and branch != registry.default_branch:
            event_trigger.match["infrahub.branch.name"] = branch

        event_trigger.match_related = {
            "prefect.resource.role": ["infrahub.node.attribute_update", "infrahub.node.relationship_update"],
            "infrahub.field.name": trigger_node.fields,
        }

        workflow = ExecuteWorkflow(
            workflow=COMPUTED_ATTRIBUTE_PROCESS_JINJA2,
            parameters={
                "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                "node_kind": "{{ event.resource['infrahub.node.kind'] }}",
                "object_id": "{{ event.resource['infrahub.node.id'] }}",
                "computed_attribute_name": computed_attribute.attribute.name,
                "computed_attribute_kind": computed_attribute.kind,
                "updated_fields": {
                    "__prefect_kind": "json",
                    "value": {
                        "__prefect_kind": "jinja",
                        "template": "{{ event.payload['data']['fields'] | tojson }}",
                    },
                },
                "context": {
                    "__prefect_kind": "json",
                    "value": {
                        "__prefect_kind": "jinja",
                        "template": "{{ event.payload['context'] | tojson }}",
                    },
                },
            },
        )

        definition = cls(
            name=f"{computed_attribute.key_name}{NAME_SEPARATOR}kind{NAME_SEPARATOR}{trigger_node.kind}",
            template_hash=template_hash,
            branch=branch,
            computed_attribute=computed_attribute,
            trigger=event_trigger,
            actions=[workflow],
        )

        return definition


class ComputedAttrPythonTriggerDefinition(TriggerBranchDefinition):
    type: TriggerType = TriggerType.COMPUTED_ATTR_PYTHON
    computed_attribute: PythonTransformComputedAttribute

    @classmethod
    def from_object(
        cls,
        branch: str,
        computed_attribute: PythonTransformComputedAttribute,
        branches_out_of_scope: list[str] | None = None,
    ) -> Self:
        # scope = registry.default_branch

        event_trigger = EventTrigger()
        event_trigger.events.update({NodeCreatedEvent.event_name, NodeUpdatedEvent.event_name})
        event_trigger.match = {
            "infrahub.node.kind": [computed_attribute.computed_attribute.kind],
        }

        if branches_out_of_scope:
            event_trigger.match["infrahub.branch.name"] = [f"!{branch}" for branch in branches_out_of_scope]
        elif not branches_out_of_scope and branch != registry.default_branch:
            event_trigger.match["infrahub.branch.name"] = branch

        update_fields = computed_attribute.query_analyzer.query_report.fields_by_kind(
            kind=computed_attribute.computed_attribute.kind
        )
        event_trigger.match_related = {
            "prefect.resource.role": ["infrahub.node.attribute_update", "infrahub.node.relationship_update"],
        }

        if update_fields and "display_label" not in update_fields:
            # The GraphQLQuery analyzer doesn't yet support figuring out which updates would match the "display label"
            # of a query. Because of this we temporarily match any field if the display_label is part of the computed
            # attribute query
            event_trigger.match_related["infrahub.field.name"] = update_fields

        definition = cls(
            name=computed_attribute.computed_attribute.key_name,
            branch=branch,
            computed_attribute=computed_attribute,
            trigger=event_trigger,
            actions=[
                ExecuteWorkflow(
                    workflow=COMPUTED_ATTRIBUTE_PROCESS_TRANSFORM,
                    parameters={
                        "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                        "node_kind": "{{ event.resource['infrahub.node.kind'] }}",
                        "object_id": "{{ event.resource['infrahub.node.id'] }}",
                        "computed_attribute_name": computed_attribute.computed_attribute.attribute.name,
                        "computed_attribute_kind": computed_attribute.computed_attribute.kind,
                        "context": {
                            "__prefect_kind": "json",
                            "value": {
                                "__prefect_kind": "jinja",
                                "template": "{{ event.payload['context'] | tojson }}",
                            },
                        },
                    },
                ),
            ],
        )

        return definition


class ComputedAttrPythonQueryTriggerDefinition(TriggerBranchDefinition):
    type: TriggerType = TriggerType.COMPUTED_ATTR_PYTHON_QUERY

    @classmethod
    def from_object(
        cls,
        branch: str,
        kind: str,
        computed_attribute: PythonTransformComputedAttribute,
        branches_out_of_scope: list[str] | None = None,
    ) -> Self:
        # Only matching on node updated events, before nodes are created they won't be a member of the GraphQL query
        # group regardless so it doesn't make sense to trigger the query on node creation. For the initial object
        # where the computed attribute belongs that to will need to be created first which will trigger its own initial
        # process to populated the original members of the GraphQL query group
        event_trigger = EventTrigger(events={NodeUpdatedEvent.event_name})
        event_trigger.match = {
            "infrahub.node.kind": kind,
        }

        update_fields = computed_attribute.query_analyzer.query_report.fields_by_kind(kind=kind)
        event_trigger.match_related = {
            "prefect.resource.role": ["infrahub.node.attribute_update", "infrahub.node.relationship_update"],
        }

        if update_fields and "display_label" not in update_fields:
            # The GraphQLQuery analyzer doesn't yet support figuring out which updates would match the "display label"
            # of a query. Because of this we temporarily match any field if the display_label is part of the computed
            # attribute query
            event_trigger.match_related["infrahub.field.name"] = update_fields

        if branches_out_of_scope:
            event_trigger.match["infrahub.branch.name"] = [f"!{branch}" for branch in branches_out_of_scope]
        elif not branches_out_of_scope and branch != registry.default_branch:
            event_trigger.match["infrahub.branch.name"] = branch

        definition = cls(
            name=f"{computed_attribute.computed_attribute.key_name}{NAME_SEPARATOR}kind{NAME_SEPARATOR}{kind}",
            branch=branch,
            trigger=event_trigger,
            actions=[
                ExecuteWorkflow(
                    workflow=QUERY_COMPUTED_ATTRIBUTE_TRANSFORM_TARGETS,
                    parameters={
                        "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                        "node_kind": "{{ event.resource['infrahub.node.kind'] }}",
                        "object_id": "{{ event.resource['infrahub.node.id'] }}",
                        "context": {
                            "__prefect_kind": "json",
                            "value": {
                                "__prefect_kind": "jinja",
                                "template": "{{ event.payload['context'] | tojson }}",
                            },
                        },
                    },
                ),
            ],
        )

        return definition


class ComputedAttrJinja2GraphQLResponse(BaseModel):
    node_id: str
    computed_attribute_value: str | None
    variables: dict[str, Any] = Field(default_factory=dict)


class ComputedAttrJinja2GraphQL(BaseModel):
    node_schema: NodeSchema = Field(..., description="The node kind where the computed attribute is defined")
    attribute_schema: AttributeSchema = Field(..., description="The computed attribute")
    variables: list[str] = Field(..., description="The list of variable names used within the computed attribute")

    def render_graphql_query(self, query_filter: str, filter_id: str) -> str:
        query_fields = self.query_fields
        query_fields["id"] = None
        query_fields[self.attribute_schema.name] = {"value": None}
        query = Query(
            name="ComputedAttributeFilter",
            query={
                self.node_schema.kind: {
                    "@filters": {query_filter: filter_id},
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

    def parse_response(self, response: dict[str, Any]) -> list[ComputedAttrJinja2GraphQLResponse]:
        rendered_response: list[ComputedAttrJinja2GraphQLResponse] = []
        if kind_payload := response.get(self.node_schema.kind):
            edges = kind_payload.get("edges", [])
            for node in edges:
                if node_response := self.to_node_response(node_dict=node):
                    rendered_response.append(node_response)
        return rendered_response

    def to_node_response(self, node_dict: dict[str, Any]) -> ComputedAttrJinja2GraphQLResponse | None:
        if node := node_dict.get("node"):
            node_id = node.get("id")
        else:
            return None

        computed_attribute = node.get(self.attribute_schema.name, {}).get("value")
        response = ComputedAttrJinja2GraphQLResponse(node_id=node_id, computed_attribute_value=computed_attribute)
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
