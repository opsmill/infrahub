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

_ADD_THING_MUTATION = """
mutation AddThing($child_id: String!, $thing_id: String!) {
    RelationshipAdd(data: { id: $child_id, name: "things", nodes: [{ id: $thing_id }] }) { ok }
}
"""

_REMOVE_THING_MUTATION = """
mutation RemoveThing($child_id: String!, $thing_id: String!) {
    RelationshipRemove(data: { id: $child_id, name: "things", nodes: [{ id: $thing_id }] }) { ok }
}
"""


@dataclass
class ThingsAndProfile:
    profile_id: str
    thing_ids: list[str]


@dataclass
class ChildWithProfile:
    child_id: str
    things_and_profile: ThingsAndProfile


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


async def _build_child_with_profile(db: InfrahubDatabase, branch: Branch, name: str) -> ChildWithProfile:
    """Create three things objects, a profile sourcing the first two, and a child with that profile applied."""
    thing_node_schema = registry.schema.get_node_schema(name=THING.kind, branch=branch, duplicate=False)
    thing_ids: list[str] = []
    for thing_name, color in [(f"{name}_eye_cover", "black"), (f"{name}_arms", "black"), (f"{name}_necklace", "white")]:
        thing = await Node.init(db=db, branch=branch, schema=thing_node_schema)
        await thing.new(db=db, name=thing_name, color=color)
        await thing.save(db=db)
        thing_ids.append(thing.id)

    profile_schema = registry.schema.get_profile_schema(name=f"Profile{CHILD.kind}", branch=branch, duplicate=False)
    profile = await Node.init(db=db, branch=branch, schema=profile_schema)
    await profile.new(db=db, profile_name=name, things=[thing_ids[0], thing_ids[1]], profile_priority=100)
    await profile.save(db=db)

    child_node_schema = registry.schema.get_node_schema(name=CHILD.kind, branch=branch, duplicate=False)
    child = await Node.init(db=db, branch=branch, schema=child_node_schema)
    await child.new(db=db, name=name, profiles=[profile.id])
    await child.save(db=db)
    applier = NodeProfilesApplier(db=db, branch=branch)
    await applier.apply_profiles(node=child)
    await child.save(db=db)

    # Sanity check: the profile sources both of its peers onto the new node.
    assert await _get_child_state_via_manager(db=db, branch=branch, child_id=child.id) == ChildState(
        thing_sources={thing_ids[0]: profile.id, thing_ids[1]: profile.id},
        profile_ids={profile.id},
    )

    return ChildWithProfile(
        child_id=child.id, things_and_profile=ThingsAndProfile(profile_id=profile.id, thing_ids=thing_ids)
    )


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
    async def child_with_profile(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, child_thing_schema: None
    ) -> ChildWithProfile:
        # Fresh data per test for tests that modify the relationship. `TestingThing.owner` is cardinality
        # one, so each test needs its own thing nodes.
        return await _build_child_with_profile(db=db, branch=default_branch_scope_class, name="augmented")

    @pytest.fixture(scope="class")
    async def base_child_with_profile(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, child_thing_schema: None
    ) -> ChildWithProfile:
        # Built once for the whole class and shared by tests that do not alter state.
        return await _build_child_with_profile(db=db, branch=default_branch_scope_class, name="base")

    def _fully_sourced_state(self, things_and_profile: ThingsAndProfile) -> ChildState:
        return ChildState(
            thing_sources={
                things_and_profile.thing_ids[0]: things_and_profile.profile_id,
                things_and_profile.thing_ids[1]: things_and_profile.profile_id,
            },
            profile_ids={things_and_profile.profile_id},
        )

    async def test_update_remove_profile_and_readd_profile_sourced_peer(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, child_with_profile: ChildWithProfile
    ) -> None:
        branch = default_branch_scope_class
        child_id = child_with_profile.child_id
        kept_peer = child_with_profile.things_and_profile.thing_ids[0]

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
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, child_with_profile: ChildWithProfile
    ) -> None:
        branch = default_branch_scope_class
        child_id = child_with_profile.child_id
        things_and_profile = child_with_profile.things_and_profile
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

    async def test_relationship_add_clears_profile_source(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, child_with_profile: ChildWithProfile
    ) -> None:
        """Adding a peer to a profile-sourced relationship makes the whole relationship user-defined.

        A relationship is either entirely profile-sourced or entirely user-defined; modifying it via
        RelationshipAdd clears the source of every peer from the profile.
        """
        branch = default_branch_scope_class
        child_id = child_with_profile.child_id
        things_and_profile = child_with_profile.things_and_profile
        profile_peers = [things_and_profile.thing_ids[0], things_and_profile.thing_ids[1]]
        new_peer = things_and_profile.thing_ids[2]

        result = await _run_graphql(
            db=db, branch=branch, query=_ADD_THING_MUTATION, variables={"child_id": child_id, "thing_id": new_peer}
        )
        assert result.errors is None
        assert result.data
        assert result.data["RelationshipAdd"]["ok"] is True

        # Every peer is now user-defined; the profile stays assigned but no longer sources the relationship.
        assert await _get_child_state_via_manager(db=db, branch=branch, child_id=child_id) == ChildState(
            thing_sources={profile_peers[0]: None, profile_peers[1]: None, new_peer: None},
            profile_ids={things_and_profile.profile_id},
        )

    async def test_relationship_remove_clears_profile_source(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, child_with_profile: ChildWithProfile
    ) -> None:
        """Removing a peer from a profile-sourced relationship makes the remaining peers user-defined.

        A relationship is either entirely profile-sourced or entirely user-defined; modifying it via
        RelationshipRemove detaches the surviving peers from the profile.
        """
        branch = default_branch_scope_class
        child_id = child_with_profile.child_id
        things_and_profile = child_with_profile.things_and_profile
        removed_peer = things_and_profile.thing_ids[0]
        remaining_peer = things_and_profile.thing_ids[1]

        result = await _run_graphql(
            db=db,
            branch=branch,
            query=_REMOVE_THING_MUTATION,
            variables={"child_id": child_id, "thing_id": removed_peer},
        )
        assert result.errors is None
        assert result.data
        assert result.data["RelationshipRemove"]["ok"] is True

        # The removed peer is gone and the surviving peer is now user-defined.
        assert await _get_child_state_via_manager(db=db, branch=branch, child_id=child_id) == ChildState(
            thing_sources={remaining_peer: None},
            profile_ids={things_and_profile.profile_id},
        )

    async def test_failed_relationship_add_does_not_clear_profile_source(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, base_child_with_profile: ChildWithProfile
    ) -> None:
        """A failed RelationshipAdd must not clear the profile source.

        Detaching happens inside the mutation transaction and after validation, so a mutation that
        fails leaves the profile-sourced peers untouched.
        """
        branch = default_branch_scope_class
        child_id = base_child_with_profile.child_id

        # Adding a non-existent peer fails the whole mutation.
        result = await _run_graphql(
            db=db,
            branch=branch,
            query=_ADD_THING_MUTATION,
            variables={"child_id": child_id, "thing_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert result.errors is not None

        # The relationship is unchanged: both peers remain sourced from the profile.
        assert await _get_child_state_via_manager(db=db, branch=branch, child_id=child_id) == self._fully_sourced_state(
            base_child_with_profile.things_and_profile
        )

    async def test_failed_relationship_remove_does_not_clear_profile_source(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, base_child_with_profile: ChildWithProfile
    ) -> None:
        """A failed RelationshipRemove must not clear the profile source."""
        branch = default_branch_scope_class
        child_id = base_child_with_profile.child_id

        result = await _run_graphql(
            db=db,
            branch=branch,
            query=_REMOVE_THING_MUTATION,
            variables={"child_id": child_id, "thing_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert result.errors is not None

        assert await _get_child_state_via_manager(db=db, branch=branch, child_id=child_id) == self._fully_sourced_state(
            base_child_with_profile.things_and_profile
        )

    async def test_relationship_add_existing_peer_does_not_clear_profile_source(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, base_child_with_profile: ChildWithProfile
    ) -> None:
        """Re-adding a peer that is already present is a no-op and must not clear the profile source.

        The source is only cleared when the relationship is actually modified.
        """
        branch = default_branch_scope_class
        child_id = base_child_with_profile.child_id
        existing_profile_peer = base_child_with_profile.things_and_profile.thing_ids[0]

        result = await _run_graphql(
            db=db,
            branch=branch,
            query=_ADD_THING_MUTATION,
            variables={"child_id": child_id, "thing_id": existing_profile_peer},
        )
        assert result.errors is None
        assert result.data
        assert result.data["RelationshipAdd"]["ok"] is True

        # Nothing was added, so the relationship still has both peers sourced from the profile.
        assert await _get_child_state_via_manager(db=db, branch=branch, child_id=child_id) == self._fully_sourced_state(
            base_child_with_profile.things_and_profile
        )
