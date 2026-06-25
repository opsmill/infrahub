from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import GraphQLError
from infrahub_sdk.protocols import CoreProposedChange as SdkCoreProposedChange

from infrahub.core.constants import InfrahubKind, ValidatorConclusion
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreProposedChange
from infrahub.proposed_change.constants import ProposedChangeState
from tests.helpers.constants import PREFECT_EVENT_WAIT_SECONDS
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator

DUPLICATE_TAG_NAME = "orange"


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

        # Merge the second branch: it collides with the just-merged "orange" tag. Re-running the
        # integrity checks at merge time detects the uniqueness violation and rejects the merge.
        pc_two.state.value = ProposedChangeState.MERGED.value
        with pytest.raises(GraphQLError, match="Unable to merge proposed change containing failing checks"):
            await pc_two.save()

        # The rejection is driven by the schema-integrity check failing on the re-run.
        proposed_change = await NodeManager.get_one(db=db, id=pc_two.id, kind=CoreProposedChange)
        assert proposed_change
        peers = await proposed_change.validations.get_peers(db=db)  # type: ignore[attr-defined]
        schema_validators = [v for v in peers.values() if v.label.value == "Schema Integrity"]
        assert schema_validators
        assert schema_validators[0].conclusion.value.value == ValidatorConclusion.FAILURE.value

        # main never ends up with two "orange" tags.
        assert await _count_main_tags(db=db, branch=default_branch, name=DUPLICATE_TAG_NAME) == 1
