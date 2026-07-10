from dataclasses import dataclass, field
from typing import Any

import pytest

from infrahub.actions.models import CoreGeneratorAction, CoreGroupAction
from infrahub.actions.parsers import parse_trigger_rule_response
from infrahub.core.constants import InfrahubKind

_MISSING = object()


def _peer(peer: dict[str, Any] | None) -> dict[str, Any]:
    return {"node": peer}


def _group_trigger_rule(
    *,
    name: str = "group-trigger",
    action: dict[str, Any] | None,
    group: Any = _MISSING,
) -> dict[str, Any]:
    if group is _MISSING:
        group = {"id": "group-1", "__typename": "CoreStandardGroup"}
    return {
        "__typename": "CoreGroupTriggerRule",
        "id": "rule-group",
        "name": {"value": name},
        "branch_scope": {"value": "all_branches"},
        "active": {"value": True},
        "member_update": {"value": "added"},
        "group": _peer(group),
        "action": _peer(action),
    }


def _node_trigger_rule(
    *,
    name: str = "node-trigger",
    action: dict[str, Any],
) -> dict[str, Any]:
    return {
        "__typename": "CoreNodeTriggerRule",
        "id": "rule-node",
        "name": {"value": name},
        "branch_scope": {"value": "all_branches"},
        "active": {"value": True},
        "node_kind": {"value": "BuiltinTag"},
        "mutation_action": {"value": "created"},
        "matches": {"edges": []},
        "action": _peer(action),
    }


def _generator_action(*, generator: Any = _MISSING) -> dict[str, Any]:
    if generator is _MISSING:
        generator = {"__typename": "CoreGeneratorDefinition", "id": "gen-def-1"}
    return {
        "__typename": "CoreGeneratorAction",
        "id": "act-generator",
        "name": {"value": "run-generator"},
        "generator": _peer(generator),
    }


def _group_action(*, group: Any = _MISSING) -> dict[str, Any]:
    if group is _MISSING:
        group = {"id": "group-1", "__typename": "CoreStandardGroup"}
    return {
        "__typename": "CoreGroupAction",
        "id": "act-group",
        "name": {"value": "add-to-group"},
        "member_action": {"value": "add_member"},
        "group": _peer(group),
    }


def _response(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    return {InfrahubKind.TRIGGERRULE: {"edges": [{"node": node} for node in nodes]}}


def test_group_trigger_with_generator_action_is_parsed() -> None:
    rules = parse_trigger_rule_response(_response([_group_trigger_rule(action=_generator_action())]))
    assert len(rules) == 1
    assert isinstance(rules[0].action, CoreGeneratorAction)
    assert rules[0].action.generator_id == "gen-def-1"


def test_node_trigger_with_group_action_is_parsed() -> None:
    rules = parse_trigger_rule_response(_response([_node_trigger_rule(action=_group_action())]))
    assert len(rules) == 1
    assert isinstance(rules[0].action, CoreGroupAction)
    assert rules[0].action.group_id == "group-1"


@dataclass
class UnresolvedCase:
    name: str
    node: dict[str, Any] = field(default_factory=dict)


UNRESOLVED_CASES = [
    UnresolvedCase(
        name="group_action_with_missing_group",
        node=_node_trigger_rule(action=_group_action(group=None), name="node-trigger"),
    ),
    UnresolvedCase(
        name="generator_action_with_missing_generator",
        node=_group_trigger_rule(action=_generator_action(generator=None)),
    ),
    UnresolvedCase(
        name="group_trigger_with_missing_group",
        node=_group_trigger_rule(action=_generator_action(), group=None),
    ),
    UnresolvedCase(
        name="rule_with_missing_action",
        node=_group_trigger_rule(action=None),
    ),
]


@pytest.mark.parametrize("case", UNRESOLVED_CASES, ids=[c.name for c in UNRESOLVED_CASES])
def test_unresolved_relationship_is_skipped_not_crashing(case: UnresolvedCase) -> None:
    # A dangling relationship (peer absent on the queried branch) must be skipped,
    # not raise and abort the whole gather.
    rules = parse_trigger_rule_response(_response([case.node]))
    assert rules == []


def test_one_bad_rule_does_not_starve_valid_rules() -> None:
    bad = _node_trigger_rule(action=_group_action(group=None), name="dangling")
    good = _node_trigger_rule(action=_group_action(), name="healthy")
    rules = parse_trigger_rule_response(_response([bad, good]))
    assert [rule.name for rule in rules] == ["healthy"]
