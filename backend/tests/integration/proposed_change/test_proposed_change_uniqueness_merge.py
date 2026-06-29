from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import GraphQLError
from infrahub_sdk.protocols import CoreProposedChange as SdkCoreProposedChange

from infrahub import config
from infrahub.core.constants import InfrahubKind, ValidatorConclusion
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import BuiltinTag, CoreProposedChange
from infrahub.proposed_change.constants import ProposedChangeState
from tests.helpers.constants import PREFECT_EVENT_WAIT_SECONDS
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from collections.abc import Generator

    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator

DUPLICATE_TAG_NAME = "orange"

BRANCH_MERGE_MUTATION = """
mutation($branch: String!) {
    BranchMerge(data: { name: $branch }) {
        ok
    }
}
"""


async def _wait_for_validators_success(db: InfrahubDatabase, proposed_change_id: str) -> None:
    """Block until the proposed change pipeline has produced passing validators.

    Raises:
        AssertionError: if the validators do not all succeed within the wait window.

    """
    for _ in range(PREFECT_EVENT_WAIT_SECONDS):
        proposed_change = await NodeManager.get_one(db=db, id=proposed_change_id, kind=CoreProposedChange)
        assert proposed_change
        peers = await proposed_change.validations.get_peers(db=db)
        if peers and all(
            validator.conclusion.value.value == ValidatorConclusion.SUCCESS.value for validator in peers.values()
        ):
            return
        await asyncio.sleep(1)
    raise AssertionError(f"Validators for proposed change {proposed_change_id} did not all succeed")


async def _count_main_tags(db: InfrahubDatabase, branch: Branch, name: str) -> int:
    tags = await NodeManager.query(db=db, schema=InfrahubKind.TAG, filters={"name__value": name}, branch=branch)
    return len(tags)


class TestProposedChangeUniquenessMerge(TestInfrahubApp):
    """Two branches independently add an object with the same unique value.

    Each proposed change is validated against an ``orange``-free ``main``, so both pass
    their uniqueness check. Once the first branch is merged, ``main`` holds an ``orange``
    tag. Merging the second branch must then be rejected by the uniqueness constraint —
    otherwise ``main`` ends up with two ``orange`` tags, violating the constraint.
    """

    @pytest.fixture(scope="class")
    async def duplicate_tag_branches(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
    ) -> tuple[str, str]:
        branch_one = await client.branch.create(branch_name="add_orange_one")
        tag_one = await Node.init(schema=InfrahubKind.TAG, db=db, branch=branch_one.name)
        await tag_one.new(db=db, name=DUPLICATE_TAG_NAME)
        await tag_one.save(db=db)

        branch_two = await client.branch.create(branch_name="add_orange_two")
        tag_two = await Node.init(schema=InfrahubKind.TAG, db=db, branch=branch_two.name)
        await tag_two.new(db=db, name=DUPLICATE_TAG_NAME)
        await tag_two.save(db=db)

        return branch_one.name, branch_two.name

    async def test_second_merge_is_blocked_by_uniqueness(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        duplicate_tag_branches: tuple[str, str],
        client: InfrahubClient,
    ) -> None:
        branch_one, branch_two = duplicate_tag_branches

        # Both proposed changes are created and validated while main has no "orange" tag,
        # so both uniqueness checks pass.
        pc_one = await client.create(
            kind=SdkCoreProposedChange,
            data={"source_branch": branch_one, "destination_branch": "main", "name": "merge-orange-one"},
        )
        await pc_one.save()
        await _wait_for_validators_success(db=db, proposed_change_id=pc_one.id)

        pc_two = await client.create(
            kind=SdkCoreProposedChange,
            data={"source_branch": branch_two, "destination_branch": "main", "name": "merge-orange-two"},
        )
        await pc_two.save()
        await _wait_for_validators_success(db=db, proposed_change_id=pc_two.id)

        # Merge the first branch: main now has a single "orange" tag.
        pc_one.state.value = ProposedChangeState.MERGED.value
        await pc_one.save()
        for _ in range(PREFECT_EVENT_WAIT_SECONDS):
            if await _count_main_tags(db=db, branch=default_branch, name=DUPLICATE_TAG_NAME) == 1:
                break
            await asyncio.sleep(1)
        assert await _count_main_tags(db=db, branch=default_branch, name=DUPLICATE_TAG_NAME) == 1

        # Merge the second branch: it collides with the just-merged "orange" tag. The merge-time
        # constraint validation detects the uniqueness violation and rejects the merge.
        pc_two.state.value = ProposedChangeState.MERGED.value
        with pytest.raises(GraphQLError, match="Unable to merge proposed change containing failing checks"):
            await pc_two.save()

        # The rejection is recorded on the schema-integrity validator.
        proposed_change = await NodeManager.get_one(db=db, id=pc_two.id, kind=CoreProposedChange)
        assert proposed_change
        peers = await proposed_change.validations.get_peers(db=db)  # type: ignore[attr-defined]
        schema_validators = [v for v in peers.values() if v.label.value == "Schema Integrity"]
        assert schema_validators
        assert schema_validators[0].conclusion.value.value == ValidatorConclusion.FAILURE.value

        # main never ends up with two "orange" tags.
        assert await _count_main_tags(db=db, branch=default_branch, name=DUPLICATE_TAG_NAME) == 1


class TestDirectMergeUniqueness(TestInfrahubApp):
    """Two branches independently add the same unique value and are merged directly (no proposed change).

    The constraint validation that guards the merge now lives in the shared merge flow, so the direct
    ``BranchMerge`` mutation must reject the second merge just like the proposed-change path does.
    """

    @pytest.fixture(scope="class")
    async def duplicate_tag_branches(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
    ) -> tuple[str, str]:
        branch_one = await client.branch.create(branch_name="direct_orange_one")
        tag_one = await Node.init(schema=InfrahubKind.TAG, db=db, branch=branch_one.name)
        await tag_one.new(db=db, name=DUPLICATE_TAG_NAME)
        await tag_one.save(db=db)

        branch_two = await client.branch.create(branch_name="direct_orange_two")
        tag_two = await Node.init(schema=InfrahubKind.TAG, db=db, branch=branch_two.name)
        await tag_two.new(db=db, name=DUPLICATE_TAG_NAME)
        await tag_two.save(db=db)

        return branch_one.name, branch_two.name

    async def test_second_direct_merge_is_blocked_by_uniqueness(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        duplicate_tag_branches: tuple[str, str],
        client: InfrahubClient,
    ) -> None:
        branch_one, branch_two = duplicate_tag_branches

        # First branch merges cleanly: main now has a single "orange" tag.
        await client.execute_graphql(query=BRANCH_MERGE_MUTATION, variables={"branch": branch_one})
        assert await _count_main_tags(db=db, branch=default_branch, name=DUPLICATE_TAG_NAME) == 1

        # Second branch collides with the just-merged tag; the merge-time constraint validation rejects it.
        with pytest.raises(GraphQLError, match=r"constraint violation on schema 'BuiltinTag'"):
            await client.execute_graphql(query=BRANCH_MERGE_MUTATION, variables={"branch": branch_two})

        # main never ends up with two "orange" tags.
        assert await _count_main_tags(db=db, branch=default_branch, name=DUPLICATE_TAG_NAME) == 1


CONFLICT_TAG_NAME = "conflict-tag"


async def _get_main_tag_description(db: InfrahubDatabase, branch: Branch, tag_id: str) -> str | None:
    tag = await NodeManager.get_one(db=db, id=tag_id, branch=branch, kind=BuiltinTag, raise_on_error=True)
    return tag.description.value


async def _wait_for_data_integrity_failure(db: InfrahubDatabase, proposed_change_id: str) -> None:
    """Block until the proposed change's Data Integrity validator reports a failure.

    Raises:
        AssertionError: if the validator does not fail within the wait window.

    """
    for _ in range(PREFECT_EVENT_WAIT_SECONDS):
        proposed_change = await NodeManager.get_one(db=db, id=proposed_change_id, kind=CoreProposedChange)
        assert proposed_change
        peers = await proposed_change.validations.get_peers(db=db)
        data_validators = [v for v in peers.values() if v.label.value == "Data Integrity"]
        if data_validators and data_validators[0].conclusion.value.value == ValidatorConclusion.FAILURE.value:
            return
        await asyncio.sleep(1)
    raise AssertionError(f"Data Integrity validator for proposed change {proposed_change_id} did not fail")


class TestProposedChangeDataConflictMerge(TestInfrahubApp):
    """Two branches edit the same field of the same node; the conflict only appears after one merges.

    Each proposed change is validated while ``main`` still holds the original value, so neither sees a
    conflict and both pass. Once the first branch is merged, ``main`` holds a new value and the second
    branch now conflicts with it. The post-merge diff update re-synchronizes the second proposed
    change's data checks, flipping its Data Integrity validator to failure, and its merge is then
    rejected by the stored data-check gate. This documents that the data-conflict TOCTOU is handled by
    existing machinery (unlike the uniqueness case, which is a constraint, not a diff conflict).
    """

    @pytest.fixture(scope="class")
    async def conflicting_description_branches(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
    ) -> tuple[str, str, str]:
        # A tag exists on main before either branch is created, so both branches edit the same node.
        tag = await Node.init(schema=InfrahubKind.TAG, db=db)
        await tag.new(db=db, name=CONFLICT_TAG_NAME, description="original")
        await tag.save(db=db)

        branch_one = await client.branch.create(branch_name="edit_desc_one")
        tag_one = await NodeManager.get_one(db=db, id=tag.id, branch=branch_one.name, kind=BuiltinTag, raise_on_error=True)
        tag_one.description.value = "from_one"
        await tag_one.save(db=db)

        branch_two = await client.branch.create(branch_name="edit_desc_two")
        tag_two = await NodeManager.get_one(db=db, id=tag.id, branch=branch_two.name, kind=BuiltinTag, raise_on_error=True)
        tag_two.description.value = "from_two"
        await tag_two.save(db=db)

        return tag.id, branch_one.name, branch_two.name

    async def test_second_merge_is_blocked_by_data_conflict(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        conflicting_description_branches: tuple[str, str, str],
        client: InfrahubClient,
    ) -> None:
        tag_id, branch_one, branch_two = conflicting_description_branches

        pc_one = await client.create(
            kind=SdkCoreProposedChange,
            data={"source_branch": branch_one, "destination_branch": "main", "name": "merge-desc-one"},
        )
        await pc_one.save()
        await _wait_for_validators_success(db=db, proposed_change_id=pc_one.id)

        pc_two = await client.create(
            kind=SdkCoreProposedChange,
            data={"source_branch": branch_two, "destination_branch": "main", "name": "merge-desc-two"},
        )
        await pc_two.save()
        await _wait_for_validators_success(db=db, proposed_change_id=pc_two.id)

        # Merge the first branch: main now holds "from_one".
        pc_one.state.value = ProposedChangeState.MERGED.value
        await pc_one.save()
        for _ in range(PREFECT_EVENT_WAIT_SECONDS):
            if await _get_main_tag_description(db=db, branch=default_branch, tag_id=tag_id) == "from_one":
                break
            await asyncio.sleep(1)
        assert await _get_main_tag_description(db=db, branch=default_branch, tag_id=tag_id) == "from_one"

        # The post-merge diff update re-synchronizes the second proposed change's data checks against
        # the new main, flipping its Data Integrity validator to failure.
        await _wait_for_data_integrity_failure(db=db, proposed_change_id=pc_two.id)

        # Merging the second branch is then rejected by the stored data-check gate.
        pc_two.state.value = ProposedChangeState.MERGED.value
        with pytest.raises(
            GraphQLError, match="Data conflicts found on branch and missing decisions about what branch to keep"
        ):
            await pc_two.save()

        # main keeps the first branch's value; the second branch is not merged.
        assert await _get_main_tag_description(db=db, branch=default_branch, tag_id=tag_id) == "from_one"


class TestProposedChangeDataConflictMergeBackstop(TestInfrahubApp):
    """Same conflict scenario, but with the post-merge diff refresh disabled.

    With ``diff_update_after_merge`` off, the second proposed change's data checks are not refreshed
    after the first merge, so the stored data-check gate is blind to the new conflict. The merge-time
    conflict gate inside the merge flow is the backstop that still recomputes the diff and rejects the
    merge, guaranteeing correctness independently of the proactive refresh.
    """

    @pytest.fixture(scope="class", autouse=True)
    def _disable_diff_update_after_merge(self) -> Generator[None]:
        original = config.SETTINGS.main.diff_update_after_merge
        config.SETTINGS.main.diff_update_after_merge = False
        yield
        config.SETTINGS.main.diff_update_after_merge = original

    @pytest.fixture(scope="class")
    async def conflicting_description_branches(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
    ) -> tuple[str, str, str]:
        tag = await Node.init(schema=InfrahubKind.TAG, db=db)
        await tag.new(db=db, name=CONFLICT_TAG_NAME, description="original")
        await tag.save(db=db)

        branch_one = await client.branch.create(branch_name="backstop_desc_one")
        tag_one = await NodeManager.get_one(db=db, id=tag.id, branch=branch_one.name, kind=BuiltinTag, raise_on_error=True)
        tag_one.description.value = "from_one"
        await tag_one.save(db=db)

        branch_two = await client.branch.create(branch_name="backstop_desc_two")
        tag_two = await NodeManager.get_one(db=db, id=tag.id, branch=branch_two.name, kind=BuiltinTag, raise_on_error=True)
        tag_two.description.value = "from_two"
        await tag_two.save(db=db)

        return tag.id, branch_one.name, branch_two.name

    async def test_merge_time_gate_blocks_conflict(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        conflicting_description_branches: tuple[str, str, str],
        client: InfrahubClient,
    ) -> None:
        tag_id, branch_one, branch_two = conflicting_description_branches

        pc_one = await client.create(
            kind=SdkCoreProposedChange,
            data={"source_branch": branch_one, "destination_branch": "main", "name": "backstop-desc-one"},
        )
        await pc_one.save()
        await _wait_for_validators_success(db=db, proposed_change_id=pc_one.id)

        pc_two = await client.create(
            kind=SdkCoreProposedChange,
            data={"source_branch": branch_two, "destination_branch": "main", "name": "backstop-desc-two"},
        )
        await pc_two.save()
        await _wait_for_validators_success(db=db, proposed_change_id=pc_two.id)

        # Merge the first branch: main now holds "from_one". No diff refresh is triggered for pc_two.
        pc_one.state.value = ProposedChangeState.MERGED.value
        await pc_one.save()
        for _ in range(PREFECT_EVENT_WAIT_SECONDS):
            if await _get_main_tag_description(db=db, branch=default_branch, tag_id=tag_id) == "from_one":
                break
            await asyncio.sleep(1)
        assert await _get_main_tag_description(db=db, branch=default_branch, tag_id=tag_id) == "from_one"

        # pc_two's stored data checks are stale-green, so the merge-time gate recomputes the diff and
        # rejects the merge on the unresolved conflict.
        pc_two.state.value = ProposedChangeState.MERGED.value
        with pytest.raises(GraphQLError, match="conflict resolution missing"):
            await pc_two.save()

        # main keeps the first branch's value; the second branch is not merged.
        assert await _get_main_tag_description(db=db, branch=default_branch, tag_id=tag_id) == "from_one"
