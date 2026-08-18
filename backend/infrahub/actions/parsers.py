from typing import Any

from infrahub.core.constants import InfrahubKind
from infrahub.log import get_logger

from .constants import BranchScope, MemberAction, MemberUpdate, RelationshipMatch, ValueMatch
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

log = get_logger()


class UnresolvedRelationshipError(Exception):
    """A required relationship of a trigger rule did not resolve to a peer.

    The relationship is defined as required in the schema, so a null peer means the
    referenced node is not visible on the branch being read (deleted, orphaned, or
    living only on another branch). The rule cannot be reconciled and is skipped.
    """

    def __init__(self, relationship_name: str) -> None:
        self.relationship_name = relationship_name
        super().__init__(f"required relationship '{relationship_name}' did not resolve to a peer")


def parse_trigger_rule_response(data: dict[str, Any]) -> list[CoreTriggerRule]:
    rules: list[CoreTriggerRule] = []
    if (kind := data.get(InfrahubKind.TRIGGERRULE)) and (edges := kind.get("edges")):
        for edge in edges:
            node = edge["node"]
            try:
                rule = _parse_graphql_node(node)
            except UnresolvedRelationshipError as exc:
                log.warning(
                    "Skipping trigger rule with an unresolved relationship",
                    trigger_rule=node.get("name", {}).get("value"),
                    trigger_rule_id=node.get("id"),
                    relationship=exc.relationship_name,
                )
                continue
            if rule:
                rules.append(rule)

    return rules


def _resolve_peer(relationship: dict[str, Any] | None, *, relationship_name: str) -> dict[str, Any]:
    node = relationship.get("node") if relationship else None
    if not node:
        raise UnresolvedRelationshipError(relationship_name=relationship_name)
    return node


def _parse_graphql_node(data: dict[str, Any]) -> CoreTriggerRule | None:
    typename = data.get("__typename")
    name = data["name"]["value"]
    active = data["active"]["value"]
    branch_scope = BranchScope.from_value(value=data["branch_scope"]["value"])
    action = _parse_graphql_action_response(data=_resolve_peer(data.get("action"), relationship_name="action"))
    match typename:
        case "CoreGroupTriggerRule":
            member_update = MemberUpdate.from_value(data["member_update"]["value"])
            group = _resolve_peer(data.get("group"), relationship_name="group")
            return CoreGroupTriggerRule(
                name=name,
                branch_scope=branch_scope,
                action=action,
                member_update=member_update,
                group_id=group["id"],
                group_kind=group["__typename"],
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
            generator = _resolve_peer(data.get("generator"), relationship_name="generator")
            return CoreGeneratorAction(generator_id=generator["id"])
        case "CoreGroupAction":
            member_action = MemberAction.from_value(data["member_action"]["value"])
            group = _resolve_peer(data.get("group"), relationship_name="group")
            return CoreGroupAction(member_action=member_action, group_id=group["id"])

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
                        modification_type=RelationshipMatch.from_value(node["modification_type"]["value"]),
                        peer=node["peer"]["value"],
                    )
                )

    return matches
