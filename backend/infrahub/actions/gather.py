from __future__ import annotations

from graphql import graphql
from infrahub_sdk.graphql import Query
from prefect import task
from prefect.cache_policies import NONE

from infrahub.core.constants import InfrahubKind
from infrahub.core.registry import registry
from infrahub.database import InfrahubDatabase  # noqa: TC001  needed for prefect flow
from infrahub.graphql.initialization import prepare_graphql_params

from .models import ActionTriggerRuleTriggerDefinition
from .parsers import parse_trigger_rule_response


@task(
    name="gather-trigger-action-rules",
    cache_policy=NONE,
)
async def gather_trigger_action_rules(db: InfrahubDatabase) -> list[ActionTriggerRuleTriggerDefinition]:
    trigger_query = Query(
        name=InfrahubKind.TRIGGERRULE,
        query={
            InfrahubKind.TRIGGERRULE: {
                "edges": {
                    "node": {
                        "__typename": None,
                        "id": None,
                        "name": {"value": None},
                        "branch_scope": {"value": None},
                        "active": {"value": None},
                        "... on CoreNodeTriggerRule": {
                            "node_kind": {"value": None},
                            "mutation_action": {"value": None},
                            "matches": {
                                "edges": {
                                    "node": {
                                        "__typename": None,
                                        "id": None,
                                        "... on CoreNodeTriggerAttributeMatch": {
                                            "attribute_name": {"value": None},
                                            "value": {"value": None},
                                            "value_previous": {"value": None},
                                            "value_match": {"value": None},
                                        },
                                        "... on CoreNodeTriggerRelationshipMatch": {
                                            "relationship_name": {"value": None},
                                            "added": {"value": None},
                                            "peer": {"value": None},
                                        },
                                    }
                                }
                            },
                        },
                        "... on CoreGroupTriggerRule": {
                            "members_added": {"value": None},
                            "group": {
                                "node": {
                                    "id": None,
                                    "__typename": None,
                                }
                            },
                        },
                        "action": {
                            "node": {
                                "__typename": None,
                                "id": None,
                                "name": {"value": None},
                                "... on CoreGroupAction": {
                                    "add_members": {"value": None},
                                    "group": {
                                        "node": {
                                            "id": None,
                                            "__typename": None,
                                        }
                                    },
                                },
                                "... on CoreGeneratorAction": {
                                    "generator": {
                                        "node": {
                                            "__typename": None,
                                            "id": None,
                                        }
                                    },
                                },
                            }
                        },
                    }
                },
            }
        },
    )
    gql_params = await prepare_graphql_params(
        db=db,
        branch=registry.default_branch,
    )
    response = await graphql(
        schema=gql_params.schema,
        source=trigger_query.render(),
        context_value=gql_params.context,
        root_value=None,
        variable_values={},
    )

    data = response.data or {}
    trigger_rules = parse_trigger_rule_response(data)
    trigger_candidates = [
        ActionTriggerRuleTriggerDefinition.from_trigger_rule(trigger_rule=trigger_rule)
        for trigger_rule in trigger_rules
        if trigger_rule.active
    ]

    return [trigger_rule for trigger_rule in trigger_candidates if trigger_rule]
