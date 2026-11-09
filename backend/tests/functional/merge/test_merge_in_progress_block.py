from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import GraphQLError

from infrahub.branch.status_checker import MERGE_IN_PROGRESS_MESSAGE
from infrahub.core import registry
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.merge.write_blocker import MergeProtectionState, MergeWriteBlocker
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices
    from tests.adapters.message_bus import BusSimulator


class TestMergeInProgressBlock(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
    ) -> None:
        await load_schema(db, schema=CAR_SCHEMA)

    async def test_writes_blocked_during_merge_and_lifted(
        self, initial_dataset: None, client: InfrahubClient, db: InfrahubDatabase, service: InfrahubServices
    ) -> None:
        source_name = "merge_in_progress_source"
        await client.branch.create(branch_name=source_name)
        await client.branch.create(branch_name="merge_in_progress_unrelated")

        # Simulate the source branch being mid-merge into the default branch.
        backend_branch = registry.branch[source_name]
        backend_branch.status = BranchStatus.MERGING
        await backend_branch.save(db=db)
        merge_write_blocker = MergeWriteBlocker(cache=service.cache)
        await merge_write_blocker.set(branch=source_name, state=MergeProtectionState.MERGING)

        try:
            # Target gate: a write to the default branch is rejected with the transient message.
            default_node = await client.create(kind="TestingPerson", name="target gate", branch="main")
            with pytest.raises(GraphQLError) as default_exc:
                await default_node.save()
            assert default_exc.value.errors[0]["message"] == MERGE_IN_PROGRESS_MESSAGE
            default_extensions = default_exc.value.errors[0]["extensions"]
            assert default_extensions["code"] == "MERGE_IN_PROGRESS"
            assert default_extensions["http_status"] == 423
            assert default_extensions["data"] == {"branch_name": "main", "merging_branch": source_name}

            # Source gate: a write to the branch being merged is rejected as read-only.
            source_node = await client.create(kind="TestingPerson", name="source gate", branch=source_name)
            with pytest.raises(GraphQLError) as source_exc:
                await source_node.save()
            assert source_exc.value.errors[0]["message"] == (
                f"Branch '{source_name}' is being merged and is read-only. No modifications are allowed."
            )
            source_extensions = source_exc.value.errors[0]["extensions"]
            assert source_extensions["code"] == "MERGE_IN_PROGRESS"
            assert source_extensions["http_status"] == 423
            assert source_extensions["data"] == {"branch_name": source_name, "merging_branch": source_name}

            # An unrelated branch stays writable.
            unrelated_node = await client.create(
                kind="TestingPerson", name="unrelated", branch="merge_in_progress_unrelated"
            )
            await unrelated_node.save()
        finally:
            await merge_write_blocker.delete()

        # Clearing the key lifts the block: a default-branch write succeeds again.
        lifted_node = await client.create(kind="TestingPerson", name="after lift", branch="main")
        await lifted_node.save()

    async def test_branch_create_and_unrelated_delete_allowed_during_merge(
        self, initial_dataset: None, client: InfrahubClient, db: InfrahubDatabase, service: InfrahubServices
    ) -> None:
        merging_name = "branch_mgmt_merging"
        unrelated_name = "branch_mgmt_unrelated_delete"
        await client.branch.create(branch_name=merging_name)
        await client.branch.create(branch_name=unrelated_name)

        backend_branch = registry.branch[merging_name]
        backend_branch.status = BranchStatus.MERGING
        await backend_branch.save(db=db)
        merge_write_blocker = MergeWriteBlocker(cache=service.cache)
        await merge_write_blocker.set(branch=merging_name, state=MergeProtectionState.MERGING)

        try:
            # Branch-management mutations are not blocked by the merge target gate: a new branch can be
            # created and an unrelated branch can be deleted while a merge is in progress.
            await client.branch.create(branch_name="branch_mgmt_created_during_merge")
            assert await client.branch.delete(branch_name=unrelated_name)

            # The branch being merged stays read-only: deleting it is rejected.
            with pytest.raises(GraphQLError) as delete_exc:
                await client.branch.delete(branch_name=merging_name)
            assert delete_exc.value.errors[0]["message"] == (
                f"Branch '{merging_name}' is being merged and is read-only. No modifications are allowed."
            )
        finally:
            await merge_write_blocker.delete()

    async def test_exempt_first_field_does_not_unblock_later_data_write(
        self, initial_dataset: None, client: InfrahubClient, db: InfrahubDatabase, service: InfrahubServices
    ) -> None:
        """A multi-field mutation must not let an exempt first field unblock a later default-branch write.

        The gate keys on the field being resolved, not on the first selection, so the trailing
        TestingPersonCreate is still rejected even though BranchCreate precedes it.
        """
        merging_name = "branch_mgmt_multifield_merging"
        await client.branch.create(branch_name=merging_name)

        backend_branch = registry.branch[merging_name]
        backend_branch.status = BranchStatus.MERGING
        await backend_branch.save(db=db)
        merge_write_blocker = MergeWriteBlocker(cache=service.cache)
        await merge_write_blocker.set(branch=merging_name, state=MergeProtectionState.MERGING)

        mutation = """
        mutation {
          BranchCreate(data: {name: "branch_mgmt_multifield_decoy"}) { ok }
          TestingPersonCreate(data: {name: {value: "multifield_smuggled_write"}}) { ok }
        }
        """
        try:
            with pytest.raises(GraphQLError) as exc:
                await client.execute_graphql(query=mutation, branch_name="main")
            assert exc.value.errors[0]["message"] == MERGE_IN_PROGRESS_MESSAGE
        finally:
            await merge_write_blocker.delete()

    async def test_successful_merge_lifts_protection(
        self, initial_dataset: None, client: InfrahubClient, db: InfrahubDatabase, service: InfrahubServices
    ) -> None:
        branch_name = "merge_clean_completion"
        await client.branch.create(branch_name=branch_name)

        node = await client.create(kind="TestingPerson", name="merge me", branch=branch_name)
        await node.save()

        success = await client.branch.merge(branch_name=branch_name)
        assert success

        # The write protection is lifted once the merge fully succeeds.
        assert await MergeWriteBlocker(cache=service.cache).get() is None

        after_merge = await client.create(kind="TestingPerson", name="after merge", branch="main")
        await after_merge.save()

    async def test_new_merge_and_rebase_rejected_while_protected(
        self, initial_dataset: None, client: InfrahubClient, db: InfrahubDatabase, service: InfrahubServices
    ) -> None:
        merging_name = "merge_blocker"
        blocked_name = "merge_blocked"
        await client.branch.create(branch_name=merging_name)
        await client.branch.create(branch_name=blocked_name)

        merge_write_blocker = MergeWriteBlocker(cache=service.cache)
        await merge_write_blocker.set(branch=merging_name, state=MergeProtectionState.MERGING)

        try:
            with pytest.raises(GraphQLError) as merge_exc:
                await client.branch.merge(branch_name=blocked_name)
            assert merge_exc.value.errors[0]["message"] == MERGE_IN_PROGRESS_MESSAGE

            with pytest.raises(GraphQLError) as rebase_exc:
                await client.branch.rebase(branch_name=blocked_name)
            assert rebase_exc.value.errors[0]["message"] == MERGE_IN_PROGRESS_MESSAGE
        finally:
            await merge_write_blocker.delete()
