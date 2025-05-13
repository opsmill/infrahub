from typing import Any

from infrahub.core.constants import InfrahubKind

from .constants import BranchScope, ValueMatch
from .models import (
    CoreAction,
    CoreGeneratorAction,
    CoreGroupAction,
    CoreGroupTriggerRule,
    CoreNodeTriggerAttributeMatch,
    CoreNodeTriggerMatch,
    CoreNodeTriggerRelationshipMatch,
    CoreNodeTriggerRule,
    CoreTriggerRule,
)


def parse_trigger_rule_response(data: dict[str, Any]) -> list[CoreTriggerRule]:
    rules: list[CoreTriggerRule] = []
    if kind := data.get(InfrahubKind.TRIGGERRULE):
        if edges := kind.get("edges"):
            for edge in edges:
                if rule := _parse_graphql_node(edge["node"]):
                    rules.append(rule)

    return rules


def _parse_graphql_node(data: dict[str, Any]) -> CoreTriggerRule | None:
    typename = data.get("__typename")
    name = data["name"]["value"]
    active = data["active"]["value"]
    branch_scope = BranchScope.from_value(value=data["branch_scope"]["value"])
    action = _parse_graphql_action_response(data=data["action"]["node"])
    match typename:
        case "CoreGroupTriggerRule":
            members_added = data["members_added"]["value"]
            group_id = data["group"]["node"]["id"]
            group_kind = data["group"]["node"]["__typename"]
            return CoreGroupTriggerRule(
                name=name,
                branch_scope=branch_scope,
                action=action,
                members_added=members_added,
                group_id=group_id,
                group_kind=group_kind,
                active=active,
            )
        case "CoreNodeTriggerRule":
            node_kind = data["node_kind"]["value"]
            mutation_action = data["mutation_action"]["value"]
            matches = _parse_node_trigger_matches(data=data["matches"]["edges"])
            return CoreNodeTriggerRule(
                name=name,
                branch_scope=branch_scope,
                action=action,
                node_kind=node_kind,
                mutation_action=mutation_action,
                matches=matches,
                active=active,
            )
    return None


def _parse_graphql_action_response(data: dict[str, Any]) -> CoreAction:
    typename = data["__typename"]
    match typename:
        case "CoreGeneratorAction":
            generator_id = data["generator"]["node"]["id"]
            return CoreGeneratorAction(generator_id=generator_id)
        case "CoreGroupAction":
            add_members = data["add_members"]["value"]
            group_id = data["group"]["node"]["id"]
            return CoreGroupAction(add_members=add_members, group_id=group_id)

    raise NotImplementedError(f"{typename} is not a valid CoreAction")


def _parse_node_trigger_matches(data: list[dict[str, Any]]) -> list[CoreNodeTriggerMatch]:
    matches: list[CoreNodeTriggerMatch] = []
    for entry in data:
        node = entry["node"]
        typename = node["__typename"]
        match typename:
            case "CoreNodeTriggerAttributeMatch":
                matches.append(
                    CoreNodeTriggerAttributeMatch(
                        attribute_name=node["attribute_name"]["value"],
                        value=node["value"]["value"],
                        value_previous=node["value_previous"]["value"],
                        value_match=ValueMatch.from_value(value=node["value_match"]["value"]),
                    )
                )
            case "CoreNodeTriggerRelationshipMatch":
                matches.append(
                    CoreNodeTriggerRelationshipMatch(
                        relationship_name=node["relationship_name"]["value"],
                        added=node["added"]["value"],
                        peer=node["peer"]["value"],
                    )
                )

    return matches
