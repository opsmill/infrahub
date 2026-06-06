import copy
from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core.branch import Branch
from infrahub.core.constants import MetadataOptions
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.registry import registry
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.graphql.initialization import prepare_graphql_params
from infrahub.profiles.node_applier import NodeProfilesApplier
from infrahub.services import InfrahubServices
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from tests.helpers.graphql import graphql
from tests.helpers.schema import CHILD, THING, load_schema

# Object selection returning the `things` peers with their source and the assigned profiles. Used in
# the mutation response so the source of each peer can be verified from the mutation itself.
_OBJECT_WITH_SOURCES = """
        object {
            profiles { edges { node { id } } }
            things {
                edges {
                    node { id }
                    properties { source { id } }
                }
            }
        }
"""


@dataclass
class ThingsAndProfile:
    profile_id: str
    thing_ids: list[str]


@dataclass
class ChildState:
    # Maps each `things` peer id to its source id, or None when the peer is not sourced from a profile.
    thing_sources: dict[str, str | None]
    profile_ids: set[str]


async def _run_graphql(db: InfrahubDatabase, branch: Branch, query: str, variables: dict[str, Any]):
    branch.update_schema_hash()
    gql_params = await prepare_graphql_params(db=db, branch=branch)
    gql_params.context.service = await InfrahubServices.new(workflow=WorkflowLocalExecution())
    return await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables,
    )


def _parse_child_state(node: dict[str, Any]) -> ChildState:
    thing_sources = {
        edge["node"]["id"]: (edge["properties"]["source"]["id"] if edge["properties"]["source"] else None)
        for edge in node["things"]["edges"]
    }
    profile_ids = {edge["node"]["id"] for edge in node["profiles"]["edges"]}
    return ChildState(thing_sources=thing_sources, profile_ids=profile_ids)


async def _get_child_state_via_manager(db: InfrahubDatabase, branch: Branch, child_id: str) -> ChildState:
    # prefetch_relationships loads the peers and their source metadata eagerly, so get_relationships()
    # is served from cache and the source can be read from `source_id` without a per-peer query.
    node = await NodeManager.get_one(
        db=db,
        branch=branch,
        id=child_id,
        include_metadata=MetadataOptions.SOURCE,
        prefetch_relationships=True,
    )
    things_manager = node.get_relationship(name="things")
    thing_sources: dict[str, str | None] = {}
    for rel in await things_manager.get_relationships(db=db):
        if not rel.peer_id:
            continue
        thing_sources[rel.peer_id] = str(rel.source_id) if rel.source_id else None
    profiles_manager = node.get_relationship(name="profiles")
    profile_ids = set((await profiles_manager.get_peers(db=db)).keys())
    return ChildState(thing_sources=thing_sources, profile_ids=profile_ids)


async def _verify_state(
    db: InfrahubDatabase, branch: Branch, child_id: str, mutation_object: dict[str, Any], expected: ChildState
) -> None:
    # The mutation response carries the resulting peers and their sources.
    assert _parse_child_state(mutation_object) == expected
    # The database matches what the mutation reported.
    assert await _get_child_state_via_manager(db=db, branch=branch, child_id=child_id) == expected


class TestProfileRelationshipOverride:
    @pytest.fixture(scope="class")
    async def child_thing_schema(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        data_schema_scope_class: None,
        register_core_models_schema_scope_class: None,
    ) -> None:
        thing_copy = copy.deepcopy(THING)
        thing_copy.relationships[0].optional = True
        await load_schema(
            db=db, schema=SchemaRoot(nodes=[CHILD, thing_copy]), branch_name=default_branch_scope_class.name
        )

    @pytest.fixture
    async def things_and_profile(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        child_thing_schema: None,
    ) -> ThingsAndProfile:
        # Fresh peers per test: `TestingThing.owner` is cardinality one, so a thing cannot be owned by
        # more than one child across tests sharing the same database.
        branch = default_branch_scope_class
        thing_node_schema = registry.schema.get_node_schema(name=THING.kind, branch=branch, duplicate=False)
        thing_ids: list[str] = []
        for name, color in [("Eye cover", "black"), ("Cybernetic arms", "black"), ("Pearl necklace", "white")]:
            thing = await Node.init(db=db, branch=branch, schema=thing_node_schema)
            await thing.new(db=db, name=name, color=color)
            await thing.save(db=db)
            thing_ids.append(thing.id)

        profile_schema = registry.schema.get_profile_schema(name=f"Profile{CHILD.kind}", branch=branch, duplicate=False)
        profile = await Node.init(db=db, branch=branch, schema=profile_schema)
        await profile.new(db=db, profile_name="augmented", things=[thing_ids[0], thing_ids[1]], profile_priority=100)
        await profile.save(db=db)

        return ThingsAndProfile(profile_id=profile.id, thing_ids=thing_ids)

    @pytest.fixture
    async def child_id(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, things_and_profile: ThingsAndProfile
    ) -> str:
        branch = default_branch_scope_class
        child_node_schema = registry.schema.get_node_schema(name=CHILD.kind, branch=branch, duplicate=False)
        child = await Node.init(db=db, branch=branch, schema=child_node_schema)
        await child.new(db=db, name="adam", profiles=[things_and_profile.profile_id])
        await child.save(db=db)
        applier = NodeProfilesApplier(db=db, branch=branch)
        await applier.apply_profiles(node=child)
        await child.save(db=db)

        # The profile sources both of its peers onto the new node
        assert await _get_child_state_via_manager(db=db, branch=branch, child_id=child.id) == ChildState(
            thing_sources={
                things_and_profile.thing_ids[0]: things_and_profile.profile_id,
                things_and_profile.thing_ids[1]: things_and_profile.profile_id,
            },
            profile_ids={things_and_profile.profile_id},
        )

        return child.id

    async def test_update_remove_profile_and_readd_profile_sourced_peer(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        things_and_profile: ThingsAndProfile,
        child_id: str,
    ) -> None:
        branch = default_branch_scope_class
        kept_peer = things_and_profile.thing_ids[0]

        # Remove the profile and explicitly set the relationship to a peer the profile used to source.
        update = (
            """
        mutation UpdateChild($child_id: String!, $thing_id: String!) {
            TestingChildUpdate(data: {
                id: $child_id,
                profiles: [],
                things: [{ id: $thing_id }],
            }) {
                ok
        """
            + _OBJECT_WITH_SOURCES
            + """
            }
        }
        """
        )
        result = await _run_graphql(
            db=db, branch=branch, query=update, variables={"child_id": child_id, "thing_id": kept_peer}
        )
        assert result.errors is None
        assert result.data
        assert result.data["TestingChildUpdate"]["ok"] is True

        # The peer is retained (not deleted with the profile) and is now user-owned with no source.
        await _verify_state(
            db=db,
            branch=branch,
            child_id=child_id,
            mutation_object=result.data["TestingChildUpdate"]["object"],
            expected=ChildState(thing_sources={kept_peer: None}, profile_ids=set()),
        )

    async def test_update_relationships_mixed_keep_profile(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        things_and_profile: ThingsAndProfile,
        child_id: str,
    ) -> None:
        branch = default_branch_scope_class
        profile_peer = things_and_profile.thing_ids[0]
        non_profile_peer = things_and_profile.thing_ids[2]

        # Override the relationship with a mix of a profile-sourced peer and a new peer, leaving the
        # profile assigned to the node.
        update = (
            """
        mutation UpdateChild($child_id: String!, $profile_peer: String!, $non_profile_peer: String!) {
            TestingChildUpdate(data: {
                id: $child_id,
                things: [{ id: $profile_peer }, { id: $non_profile_peer }],
            }) {
                ok
        """
            + _OBJECT_WITH_SOURCES
            + """
            }
        }
        """
        )
        result = await _run_graphql(
            db=db,
            branch=branch,
            query=update,
            variables={"child_id": child_id, "profile_peer": profile_peer, "non_profile_peer": non_profile_peer},
        )
        assert result.errors is None
        assert result.data
        assert result.data["TestingChildUpdate"]["ok"] is True

        # The overlapping profile peer is kept (not removed) but loses its source; the whole relationship
        # is now user-owned even though the profile remains assigned.
        await _verify_state(
            db=db,
            branch=branch,
            child_id=child_id,
            mutation_object=result.data["TestingChildUpdate"]["object"],
            expected=ChildState(
                thing_sources={profile_peer: None, non_profile_peer: None}, profile_ids={things_and_profile.profile_id}
            ),
        )

    async def test_relationship_add_new_peer_keeps_existing_profile_sources(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        things_and_profile: ThingsAndProfile,
        child_id: str,
    ) -> None:
        """Tests that adding a new peer via RelationshipAdd does not affect the sources of existing peers

        This does not need to remain the case. It is codified in this test to prevent it from unexpectedly changing
        """
        branch = default_branch_scope_class
        existing_profile_peers = [things_and_profile.thing_ids[0], things_and_profile.thing_ids[1]]
        new_peer = things_and_profile.thing_ids[2]

        # Add a single new peer to the profile-sourced relationship.
        add = """
        mutation AddThing($child_id: String!, $thing_id: String!) {
            RelationshipAdd(data: {
                id: $child_id,
                name: "things",
                nodes: [{ id: $thing_id }],
            }) {
                ok
            }
        }
        """
        result = await _run_graphql(
            db=db, branch=branch, query=add, variables={"child_id": child_id, "thing_id": new_peer}
        )
        assert result.errors is None
        assert result.data
        assert result.data["RelationshipAdd"]["ok"] is True

        # RelationshipAdd does not re-apply profiles for an ordinary relationship: the pre-existing peers
        # keep their profile source and only the newly-added peer is user-owned.
        assert await _get_child_state_via_manager(db=db, branch=branch, child_id=child_id) == ChildState(
            thing_sources={
                existing_profile_peers[0]: things_and_profile.profile_id,
                existing_profile_peers[1]: things_and_profile.profile_id,
                new_peer: None,
            },
            profile_ids={things_and_profile.profile_id},
        )

    @pytest.mark.xfail(reason="Profile changes are not propagated to a mixed relationship; see docstring.", strict=True)
    async def test_profile_change_propagates_to_mixed_relationship(
        self,
        db: InfrahubDatabase,
        default_branch_scope_class: Branch,
        things_and_profile: ThingsAndProfile,
        child_id: str,
    ) -> None:
        """Profile changes should propagate to the profile-sourced portion of a mixed relationship.

        A mixed relationship holds both profile-sourced and user-owned peers. When the profile drops
        one of its peers, that peer should be removed from the node while the still-sourced peer and
        the user-owned peer remain.

        This currently fails: NodeProfilesApplier._get_rel_names_for_profiles
        (backend/infrahub/profiles/node_applier.py) gates on the relationship-manager-level
        `is_from_profile`, which RelationshipManager.fetch_relationship_ids
        (backend/infrahub/core/relationship/model.py) computes as `all(peer.is_from_profile ...)`. A
        mixed relationship therefore reports is_from_profile=False and is excluded from reconciliation,
        so its profile-sourced peers are frozen and never updated or removed when the profile changes.
        Fixing it requires either
        - reconciling the profile-sourced portion per-peer instead of treating the
        relationship as all-or-nothing
        - or ensuring that relationship are either all profile-sourced or none of them are
        """
        branch = default_branch_scope_class
        # thing_ids[1] is the profile peer that gets dropped from the profile below.
        kept_profile_peer = things_and_profile.thing_ids[0]
        user_peer = things_and_profile.thing_ids[2]

        # Produce a mixed relationship: profile sources thing0 + thing1, user adds thing2.
        add = """
        mutation AddThing($child_id: String!, $thing_id: String!) {
            RelationshipAdd(data: { id: $child_id, name: "things", nodes: [{ id: $thing_id }] }) { ok }
        }
        """
        result = await _run_graphql(
            db=db, branch=branch, query=add, variables={"child_id": child_id, "thing_id": user_peer}
        )
        assert result.errors is None

        # Change the profile so it no longer sources thing1.
        profile_update = """
        mutation UpdateProfile($profile_id: String!, $thing_id: String!) {
            ProfileTestingChildUpdate(data: { id: $profile_id, things: [{ id: $thing_id }] }) { ok }
        }
        """
        result = await _run_graphql(
            db=db,
            branch=branch,
            query=profile_update,
            variables={"profile_id": things_and_profile.profile_id, "thing_id": kept_profile_peer},
        )
        assert result.errors is None

        # Re-apply the profiles to the child. In production a Prefect automation does this when the
        # profile changes; that automation does not run in component tests, so trigger it explicitly.
        refresh = """
        mutation RefreshProfiles($child_id: String!) {
            InfrahubProfilesRefresh(data: { id: $child_id }) { ok }
        }
        """
        result = await _run_graphql(db=db, branch=branch, query=refresh, variables={"child_id": child_id})
        assert result.errors is None

        # Desired behavior: the profile-sourced peer the profile dropped (thing1) is removed, the still-
        # sourced peer (thing0) stays profile-sourced, and the user peer (thing2) is untouched.
        assert await _get_child_state_via_manager(db=db, branch=branch, child_id=child_id) == ChildState(
            thing_sources={kept_profile_peer: things_and_profile.profile_id, user_peer: None},
            profile_ids={things_and_profile.profile_id},
        )
