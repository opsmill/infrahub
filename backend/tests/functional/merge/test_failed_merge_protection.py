from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import GraphQLError

from infrahub.branch.status_checker import MERGE_RECOVERY_REQUIRED_MESSAGE
from infrahub.core import registry
from infrahub.core.branch.enums import BranchStatus
from infrahub.core.merge.failure_recovery import scan_for_failed_merges
from infrahub.core.merge.write_blocker import MergeProtection, MergeProtectionState, MergeWriteBlocker
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices
    from tests.adapters.message_bus import BusSimulator


class TestFailedMergeProtection(TestInfrahubApp):
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

    @pytest.fixture
    async def failed_merge_source(
        self, initial_dataset: None, client: InfrahubClient, db: InfrahubDatabase, service: InfrahubServices
    ) -> AsyncGenerator[str, None]:
        """A source branch flipped to MERGE_FAILED with the write-protection key held.

        Simulates detection having marked a dead merge; resets the branch to OPEN and clears the key
        on teardown so the class-shared app is left clean.
        """
        source_name = "failed_merge_source"
        await client.branch.create(branch_name=source_name)

        backend_branch = registry.branch[source_name]
        backend_branch.status = BranchStatus.MERGE_FAILED
        await backend_branch.save(db=db)
        merge_write_blocker = MergeWriteBlocker(cache=service.cache)
        await merge_write_blocker.set(branch=source_name, state=MergeProtectionState.MERGE_FAILED)

        yield source_name

        await merge_write_blocker.delete()
        backend_branch.status = BranchStatus.OPEN
        await backend_branch.save(db=db)

    async def test_failed_merge_blocks_with_recovery_code(
        self, failed_merge_source: str, client: InfrahubClient, db: InfrahubDatabase, service: InfrahubServices
    ) -> None:
        source_name = failed_merge_source
        await client.branch.create(branch_name="failed_merge_unrelated")
        merge_write_blocker = MergeWriteBlocker(cache=service.cache)

        # Target gate: the default branch is rejected with the recovery code, not the transient one.
        default_node = await client.create(kind="TestingPerson", name="failed target gate", branch="main")
        with pytest.raises(GraphQLError) as default_exc:
            await default_node.save()
        assert default_exc.value.errors[0]["message"] == MERGE_RECOVERY_REQUIRED_MESSAGE
        default_extensions = default_exc.value.errors[0]["extensions"]
        assert default_extensions["code"] == "MERGE_RECOVERY_REQUIRED"
        assert default_extensions["http_status"] == 423
        assert default_extensions["data"] == {"branch_name": "main", "merging_branch": source_name}

        # Source gate: the failed source branch is also blocked with the recovery code.
        source_node = await client.create(kind="TestingPerson", name="failed source gate", branch=source_name)
        with pytest.raises(GraphQLError) as source_exc:
            await source_node.save()
        assert source_exc.value.errors[0]["message"] == MERGE_RECOVERY_REQUIRED_MESSAGE
        source_extensions = source_exc.value.errors[0]["extensions"]
        assert source_extensions["code"] == "MERGE_RECOVERY_REQUIRED"
        assert source_extensions["data"] == {"branch_name": source_name, "merging_branch": source_name}

        # An unrelated branch stays writable.
        unrelated_node = await client.create(
            kind="TestingPerson", name="failed unrelated", branch="failed_merge_unrelated"
        )
        await unrelated_node.save()

        # Protection survives a restart/cache flush: a scan restores the key from the durable
        # MERGE_FAILED status, and the default branch stays blocked with the recovery code.
        await merge_write_blocker.delete()
        await scan_for_failed_merges(db=db, service=service)
        assert await merge_write_blocker.get() == MergeProtection(
            branch=source_name, state=MergeProtectionState.MERGE_FAILED
        )

        after_restart = await client.create(kind="TestingPerson", name="after restart", branch="main")
        with pytest.raises(GraphQLError) as restart_exc:
            await after_restart.save()
        assert restart_exc.value.errors[0]["extensions"]["code"] == "MERGE_RECOVERY_REQUIRED"
