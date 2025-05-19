from typing import Self

from pydantic import BaseModel

from infrahub.core.registry import registry
from infrahub.events import (
    GroupMemberAddedEvent,
    GroupMemberRemovedEvent,
    NodeCreatedEvent,
    NodeDeletedEvent,
    NodeUpdatedEvent,
)
from infrahub.trigger.models import (
    EventTrigger,
    ExecuteWorkflow,
    TriggerDefinition,
    TriggerType,
)
from infrahub.workflows.catalogue import (
    ACTION_ADD_NODE_TO_GROUP,
    ACTION_RUN_GENERATOR,
    ACTION_RUN_GENERATOR_GROUP_EVENT,
    REMOVE_ADD_NODE_FROM_GROUP,
)

from .constants import BranchScope, ValueMatch


class EventGroupMember(BaseModel):
    id: str
    kind: str


class CoreAction(BaseModel):
    """CoreAction generic"""


class CoreGeneratorAction(CoreAction):
    generator_id: str


class CoreGroupAction(CoreAction):
    add_members: bool
    group_id: str


class CoreTriggerRule(BaseModel):
    name: str
    branch_scope: BranchScope
    action: CoreAction
    active: bool


class CoreGroupTriggerRule(CoreTriggerRule):
    members_added: bool
    group_id: str
    group_kind: str


class CoreNodeTriggerMatch(BaseModel):
    """Node Trigger Match Generic"""


class CoreNodeTriggerAttributeMatch(CoreNodeTriggerMatch):
    attribute_name: str
    value: str | None
    value_previous: str | None
    value_match: ValueMatch


class CoreNodeTriggerRelationshipMatch(CoreNodeTriggerMatch):
    relationship_name: str
    added: bool
    peer: str | None


class CoreNodeTriggerRule(CoreTriggerRule):
    node_kind: str
    mutation_action: str
    matches: list[CoreNodeTriggerMatch]


class ActionTriggerRuleTriggerDefinition(TriggerDefinition):
    type: TriggerType = TriggerType.ACTION_TRIGGER_RULE

    @classmethod
    def from_trigger_rule(cls, trigger_rule: CoreTriggerRule) -> Self | None:
        if isinstance(trigger_rule, CoreNodeTriggerRule):
            return cls._from_node_trigger(trigger_rule=trigger_rule)

        if isinstance(trigger_rule, CoreGroupTriggerRule):
            return cls._from_group_trigger(trigger_rule=trigger_rule)

        return None

    @classmethod
    def _from_node_trigger(
        cls,
        trigger_rule: CoreNodeTriggerRule,
    ) -> Self:
        event_trigger = EventTrigger()

        match trigger_rule.mutation_action:
            case "created":
                event_trigger.events.add(NodeCreatedEvent.event_name)
            case "deleted":
                event_trigger.events.add(NodeDeletedEvent.event_name)
            case "updated":
                event_trigger.events.add(NodeUpdatedEvent.event_name)

        event_trigger.match = {"infrahub.node.kind": trigger_rule.node_kind}

        match trigger_rule.branch_scope:
            case BranchScope.DEFAULT_BRANCH:
                event_trigger.match["infrahub.branch.name"] = registry.default_branch
            case BranchScope.OTHER_BRANCHES:
                event_trigger.match["infrahub.branch.name"] = f"!{registry.default_branch}"

        related_matches: list[dict[str, str | list[str]]] = []
        for match in trigger_rule.matches:
            if isinstance(match, CoreNodeTriggerAttributeMatch):
                match_related: dict[str, str | list[str]] = {
                    "prefect.resource.role": "infrahub.node.attribute_update",
                    "infrahub.field.name": match.attribute_name,
                    "infrahub.attribute.action": ["added", "updated", "removed"],
                }

                match match.value_match:
                    case ValueMatch.VALUE:
                        match_related["infrahub.attribute.value"] = match.value or ""
                    case ValueMatch.VALUE_PREVIOUS:
                        match_related["infrahub.attribute.value_previous"] = match.value_previous or ""
                    case ValueMatch.VALUE_FULL:
                        match_related["infrahub.attribute.value"] = match.value or ""
                        match_related["infrahub.attribute.value_previous"] = match.value_previous or ""

            elif isinstance(match, CoreNodeTriggerRelationshipMatch):
                peer_status = "added" if match.added else "removed"
                match_related = {
                    "prefect.resource.role": "infrahub.node.relationship_update",
                    "infrahub.field.name": match.relationship_name,
                    "infrahub.relationship.peer_status": peer_status,
                }
                if isinstance(match.peer, str):
                    match_related["infrahub.relationship.peer_id"] = match.peer
            related_matches.append(match_related)

        event_trigger.match_related = related_matches or {}

        if isinstance(trigger_rule.action, CoreGeneratorAction):
            workflow = ExecuteWorkflow(
                workflow=ACTION_RUN_GENERATOR,
                parameters={
                    "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                    "generator_definition_id": trigger_rule.action.generator_id,
                    "node_ids": ["{{ event.resource['infrahub.node.id'] }}"],
                    "context": {
                        "__prefect_kind": "json",
                        "value": {
                            "__prefect_kind": "jinja",
                            "template": "{{ event.payload['context'] | tojson }}",
                        },
                    },
                },
            )
        elif isinstance(trigger_rule.action, CoreGroupAction):
            if trigger_rule.action.add_members:
                flow = ACTION_ADD_NODE_TO_GROUP
            else:
                flow = REMOVE_ADD_NODE_FROM_GROUP

            workflow = ExecuteWorkflow(
                workflow=flow,
                parameters={
                    "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                    "group_id": trigger_rule.action.group_id,
                    "node_id": "{{ event.resource['infrahub.node.id'] }}",
                    "context": {
                        "__prefect_kind": "json",
                        "value": {
                            "__prefect_kind": "jinja",
                            "template": "{{ event.payload['context'] | tojson }}",
                        },
                    },
                },
            )

        return cls(
            name=trigger_rule.name,
            trigger=event_trigger,
            actions=[workflow],
        )

    @classmethod
    def _from_group_trigger(
        cls,
        trigger_rule: CoreGroupTriggerRule,
    ) -> Self:
        event_trigger = EventTrigger()

        if trigger_rule.members_added:
            event_trigger.events.add(GroupMemberAddedEvent.event_name)
        else:
            event_trigger.events.add(GroupMemberRemovedEvent.event_name)

        event_trigger.match = {"infrahub.node.kind": trigger_rule.group_kind, "infrahub.node.id": trigger_rule.group_id}

        match trigger_rule.branch_scope:
            case BranchScope.DEFAULT_BRANCH:
                event_trigger.match["infrahub.branch.name"] = registry.default_branch
            case BranchScope.OTHER_BRANCHES:
                event_trigger.match["infrahub.branch.name"] = f"!{registry.default_branch}"

        if isinstance(trigger_rule.action, CoreGeneratorAction):
            workflow = ExecuteWorkflow(
                workflow=ACTION_RUN_GENERATOR_GROUP_EVENT,
                parameters={
                    "branch_name": "{{ event.resource['infrahub.branch.name'] }}",
                    "generator_definition_id": trigger_rule.action.generator_id,
                    "members": {
                        "__prefect_kind": "json",
                        "value": {
                            "__prefect_kind": "jinja",
                            "template": "{{ event.payload['data']['members']| tojson }}",
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

        return cls(
            name=trigger_rule.name,
            trigger=event_trigger,
            actions=[workflow],
        )
