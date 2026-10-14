from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.branch import BranchStatus
from infrahub_sdk.exceptions import GraphQLError
from infrahub_sdk.protocols import CoreFileCheck, CoreGenericRepository, CoreProposedChange, CoreStandardCheck

from infrahub.core.constants import (
    InfrahubKind,
    RepositoryInternalStatus,
    RepositorySyncStatus,
    ValidatorConclusion,
    ValidatorState,
)
from infrahub.core.manager import NodeManager
from infrahub.core.protocols import CoreValidator
from infrahub.git.constants import IMPORT_STATUS_CHECK_KIND, IMPORT_STATUS_CHECK_NAME, MERGE_CONFLICT_CHECK_KIND
from infrahub.proposed_change.constants import ProposedChangeState
from tests.helpers.constants import PREFECT_EVENT_WAIT_SECONDS
from tests.helpers.file_repo import FileRepo
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.core.protocols import CoreProposedChange as InternalCoreProposedChange
    from infrahub.database import InfrahubDatabase
    from tests.adapters.message_bus import BusSimulator

BRANCH_NAME = "repository-import-status"
INHERITED_BRANCH_NAME = "repository-import-status-inherited"
REBASED_BRANCH_NAME = "repository-import-status-rebased"
DEACTIVATED_BRANCH_NAME = "repository-import-status-deactivated"
INCOMPLETE_BRANCH_NAME = "repository-import-status-incomplete"
MANAGED_REPOSITORY = "core-repo"
READ_ONLY_REPOSITORY = "read-only-repo"
RERUN_REPOSITORY_CHECKS = """
mutation RunRepositoryChecks($id: String!) {
    CoreProposedChangeRunCheck(data: {id: $id, check_type: REPOSITORY}) {
        ok
    }
}
"""


def _expected_message(repository_name: str) -> str:
    return (
        f"The last import of the objects from repository '{repository_name}' on branch '{BRANCH_NAME}' failed, so "
        f"the objects registered for this repository do not match the content of the branch. Merging would apply "
        f"the rest of the branch without them. Review the latest 'Import objects' task for this repository, "
        f"resolve the cause and run the checks again."
    )


class TestProposedChangeRepositoryImportStatus(TestInfrahubApp):
    """A proposed change must report, and refuse to merge over, a failed object import on its source branch."""

    @pytest.fixture(scope="class")
    async def repository_ids(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
        bus_simulator: BusSimulator,
        prefect_test_fixture: None,
    ) -> dict[str, str]:
        FileRepo(name=MANAGED_REPOSITORY, sources_directory=git_repos_source_dir_module_scope)
        managed = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={
                "name": MANAGED_REPOSITORY,
                "location": f"{git_repos_source_dir_module_scope}/{MANAGED_REPOSITORY}",
            },
        )
        await managed.save()

        FileRepo(name=READ_ONLY_REPOSITORY, sources_directory=git_repos_source_dir_module_scope)
        read_only = await client.create(
            kind=InfrahubKind.READONLYREPOSITORY,
            data={
                "name": READ_ONLY_REPOSITORY,
                "location": f"{git_repos_source_dir_module_scope}/{READ_ONLY_REPOSITORY}",
                "ref": "main",
            },
        )
        await read_only.save()

        return {MANAGED_REPOSITORY: managed.id, READ_ONLY_REPOSITORY: read_only.id}

    @pytest.fixture(scope="class")
    async def proposed_change_id(self, repository_ids: dict[str, str], client: InfrahubClient) -> str:
        await client.branch.create(branch_name=BRANCH_NAME, sync_with_git=True)
        for repository_id in repository_ids.values():
            await self._set_sync_status(
                client=client,
                repository_id=repository_id,
                branch=BRANCH_NAME,
                status=RepositorySyncStatus.ERROR_IMPORT,
            )

        proposed_change = await client.create(
            kind=CoreProposedChange,
            data={"source_branch": BRANCH_NAME, "destination_branch": "main", "name": "import-status"},
        )
        await proposed_change.save()
        return proposed_change.id

    @staticmethod
    async def _set_sync_status(
        client: InfrahubClient, repository_id: str, branch: str, status: RepositorySyncStatus
    ) -> None:
        repository = await client.get(kind=CoreGenericRepository, id=repository_id, branch=branch)
        repository.sync_status.value = status.value
        await repository.save()

    @staticmethod
    async def _get_validator_states(db: InfrahubDatabase, proposed_change_id: str) -> dict[str | None, tuple[str, str]]:
        proposed_change: InternalCoreProposedChange = await NodeManager.get_one(
            db=db, id=proposed_change_id, kind=InfrahubKind.PROPOSEDCHANGE, raise_on_error=True
        )
        peers = await proposed_change.validations.get_peers(db=db, peer_type=CoreValidator)
        return {peer.label.value: (peer.state.value.value, peer.conclusion.value.value) for peer in peers.values()}

    @staticmethod
    async def _wait_for_repository_validator(
        db: InfrahubDatabase, proposed_change_id: str, name: str, conclusion: ValidatorConclusion
    ) -> CoreValidator:
        """Return the repository validator for `name` once it reports `conclusion`.

        Raises:
            AssertionError: if it does not reach that conclusion within the wait window.

        """
        label = f"Repository Validator: {name}"
        for _ in range(PREFECT_EVENT_WAIT_SECONDS):
            proposed_change: InternalCoreProposedChange = await NodeManager.get_one(
                db=db, id=proposed_change_id, kind=InfrahubKind.PROPOSEDCHANGE, raise_on_error=True
            )
            peers = await proposed_change.validations.get_peers(db=db, peer_type=CoreValidator)
            validators = [peer for peer in peers.values() if peer.label.value == label]
            if len(validators) == 1 and validators[0].conclusion.value.value == conclusion.value:
                return validators[0]
            await asyncio.sleep(1)
        raise AssertionError(f"'{label}' did not reach conclusion '{conclusion.value}'")

    @pytest.mark.parametrize("repository_name", [MANAGED_REPOSITORY, READ_ONLY_REPOSITORY])
    async def test_failed_import_fails_the_repository_validator(
        self, db: InfrahubDatabase, proposed_change_id: str, client: InfrahubClient, repository_name: str
    ) -> None:
        validator = await self._wait_for_repository_validator(
            db=db,
            proposed_change_id=proposed_change_id,
            name=repository_name,
            conclusion=ValidatorConclusion.FAILURE,
        )

        checks = await client.filters(kind=CoreStandardCheck, validator__ids=validator.id)
        assert [check.name.value for check in checks] == [IMPORT_STATUS_CHECK_NAME]
        check = checks[0]
        assert (check.kind.value, check.conclusion.value, check.severity.value, check.message.value) == (
            IMPORT_STATUS_CHECK_KIND,
            ValidatorConclusion.FAILURE.value,
            "critical",
            _expected_message(repository_name),
        )

    async def test_proposed_change_refuses_to_merge(
        self, db: InfrahubDatabase, proposed_change_id: str, client: InfrahubClient
    ) -> None:
        states = await self._get_validator_states(db=db, proposed_change_id=proposed_change_id)
        assert {state for state, _ in states.values()} == {ValidatorState.COMPLETED.value}
        failing = {
            label for label, (_, conclusion) in states.items() if conclusion != ValidatorConclusion.SUCCESS.value
        }
        assert failing == {
            f"Repository Validator: {MANAGED_REPOSITORY}",
            f"Repository Validator: {READ_ONLY_REPOSITORY}",
        }

        proposed_change = await client.get(kind=CoreProposedChange, id=proposed_change_id)
        proposed_change.state.value = ProposedChangeState.MERGED.value

        with pytest.raises(GraphQLError, match=r"Unable to merge proposed change containing failing checks"):
            await proposed_change.save()

        proposed_change_after = await client.get(kind=CoreProposedChange, id=proposed_change_id)
        assert proposed_change_after.state.value == ProposedChangeState.OPEN.value

    async def test_branch_merge_refuses_a_failed_import(self, proposed_change_id: str, client: InfrahubClient) -> None:
        with pytest.raises(GraphQLError) as excinfo:
            await client.branch.merge(branch_name=BRANCH_NAME)

        assert [error["message"] for error in excinfo.value.errors] == [
            f"Cannot merge. The last import of repositories '{MANAGED_REPOSITORY}', '{READ_ONLY_REPOSITORY}' failed: "
            f"push a fix, reimport the current commit, or set the repositories to inactive."
        ]
        branch = await client.branch.get(branch_name=BRANCH_NAME)
        assert branch.status == BranchStatus.OPEN

        for branch_name in ("main", BRANCH_NAME):
            tag = await client.create(kind=InfrahubKind.TAG, branch=branch_name, data={"name": f"after-{branch_name}"})
            await tag.save()
            stored = await client.get(kind=InfrahubKind.TAG, id=tag.id, branch=branch_name)
            assert stored.name.value == f"after-{branch_name}"

    async def test_checks_clear_once_the_imports_succeed(
        self,
        db: InfrahubDatabase,
        proposed_change_id: str,
        repository_ids: dict[str, str],
        client: InfrahubClient,
    ) -> None:
        for repository_id in repository_ids.values():
            await self._set_sync_status(
                client=client, repository_id=repository_id, branch=BRANCH_NAME, status=RepositorySyncStatus.IN_SYNC
            )
        await client.execute_graphql(query=RERUN_REPOSITORY_CHECKS, variables={"id": proposed_change_id})

        for repository_name in repository_ids:
            validator = await self._wait_for_repository_validator(
                db=db,
                proposed_change_id=proposed_change_id,
                name=repository_name,
                conclusion=ValidatorConclusion.SUCCESS,
            )

            checks = await client.filters(kind=CoreStandardCheck, validator__ids=validator.id)
            assert [check.name.value for check in checks] == [IMPORT_STATUS_CHECK_NAME]
            check = checks[0]
            assert (check.conclusion.value, check.severity.value, check.message.value) == (
                ValidatorConclusion.SUCCESS.value,
                "info",
                "",
            )

        proposed_change = await client.get(kind=CoreProposedChange, id=proposed_change_id)
        proposed_change.state.value = ProposedChangeState.MERGED.value
        await proposed_change.save()

        proposed_change_after = await client.get(kind=CoreProposedChange, id=proposed_change_id)
        assert proposed_change_after.state.value == ProposedChangeState.MERGED.value

    async def test_status_inherited_from_the_default_branch_is_ignored(
        self, db: InfrahubDatabase, repository_ids: dict[str, str], client: InfrahubClient
    ) -> None:
        """A branch created while the default branch was in error keeps reading that frozen status."""
        for repository_id in repository_ids.values():
            await self._set_sync_status(
                client=client, repository_id=repository_id, branch="main", status=RepositorySyncStatus.ERROR_IMPORT
            )
        await client.branch.create(branch_name=INHERITED_BRANCH_NAME, sync_with_git=False)
        for repository_id in repository_ids.values():
            await self._set_sync_status(
                client=client, repository_id=repository_id, branch="main", status=RepositorySyncStatus.IN_SYNC
            )

        for repository_id in repository_ids.values():
            repository = await client.get(kind=CoreGenericRepository, id=repository_id, branch=INHERITED_BRANCH_NAME)
            assert repository.sync_status.value == RepositorySyncStatus.ERROR_IMPORT.value

        proposed_change = await client.create(
            kind=CoreProposedChange,
            data={"source_branch": INHERITED_BRANCH_NAME, "destination_branch": "main", "name": "inherited-status"},
        )
        await proposed_change.save()

        for repository_name in repository_ids:
            validator = await self._wait_for_repository_validator(
                db=db,
                proposed_change_id=proposed_change.id,
                name=repository_name,
                conclusion=ValidatorConclusion.SUCCESS,
            )
            checks = await client.filters(kind=CoreStandardCheck, validator__ids=validator.id)
            assert [(check.name.value, check.conclusion.value) for check in checks] == [
                (IMPORT_STATUS_CHECK_NAME, ValidatorConclusion.SUCCESS.value)
            ]

    async def test_status_recorded_on_the_branch_survives_a_rebase(
        self, db: InfrahubDatabase, repository_ids: dict[str, str], client: InfrahubClient
    ) -> None:
        """A rebase moves the branch's own edges to `branched_from`, so the recorded failure must still count."""
        await client.branch.create(branch_name=REBASED_BRANCH_NAME, sync_with_git=False)
        for repository_id in repository_ids.values():
            await self._set_sync_status(
                client=client,
                repository_id=repository_id,
                branch=REBASED_BRANCH_NAME,
                status=RepositorySyncStatus.ERROR_IMPORT,
            )
        await client.branch.rebase(branch_name=REBASED_BRANCH_NAME)

        for repository_id in repository_ids.values():
            repository = await client.get(kind=CoreGenericRepository, id=repository_id, branch=REBASED_BRANCH_NAME)
            assert repository.sync_status.value == RepositorySyncStatus.ERROR_IMPORT.value

        proposed_change = await client.create(
            kind=CoreProposedChange,
            data={"source_branch": REBASED_BRANCH_NAME, "destination_branch": "main", "name": "rebased-status"},
        )
        await proposed_change.save()

        for repository_name in repository_ids:
            validator = await self._wait_for_repository_validator(
                db=db,
                proposed_change_id=proposed_change.id,
                name=repository_name,
                conclusion=ValidatorConclusion.FAILURE,
            )
            checks = await client.filters(kind=CoreStandardCheck, validator__ids=validator.id)
            assert [(check.name.value, check.conclusion.value) for check in checks] == [
                (IMPORT_STATUS_CHECK_NAME, ValidatorConclusion.FAILURE.value)
            ]

    async def test_deactivating_the_repository_clears_the_failure(
        self, db: InfrahubDatabase, repository_ids: dict[str, str], client: InfrahubClient
    ) -> None:
        """Deactivating a repository on the branch passes its import check and drops its merge-conflict check."""
        await client.branch.create(branch_name=DEACTIVATED_BRANCH_NAME, sync_with_git=True)
        for repository_id in repository_ids.values():
            await self._set_sync_status(
                client=client,
                repository_id=repository_id,
                branch=DEACTIVATED_BRANCH_NAME,
                status=RepositorySyncStatus.ERROR_IMPORT,
            )

        proposed_change = await client.create(
            kind=CoreProposedChange,
            data={"source_branch": DEACTIVATED_BRANCH_NAME, "destination_branch": "main", "name": "deactivated"},
        )
        await proposed_change.save()

        managed_validator = await self._wait_for_repository_validator(
            db=db,
            proposed_change_id=proposed_change.id,
            name=MANAGED_REPOSITORY,
            conclusion=ValidatorConclusion.FAILURE,
        )
        merge_conflict_checks = await client.filters(kind=CoreFileCheck, validator__ids=managed_validator.id)
        assert [check.kind.value for check in merge_conflict_checks] == [MERGE_CONFLICT_CHECK_KIND]

        for repository_id in repository_ids.values():
            repository = await client.get(kind=CoreGenericRepository, id=repository_id, branch=DEACTIVATED_BRANCH_NAME)
            repository.internal_status.value = RepositoryInternalStatus.INACTIVE.value
            await repository.save()
        await client.execute_graphql(query=RERUN_REPOSITORY_CHECKS, variables={"id": proposed_change.id})

        for repository_name in repository_ids:
            validator = await self._wait_for_repository_validator(
                db=db,
                proposed_change_id=proposed_change.id,
                name=repository_name,
                conclusion=ValidatorConclusion.SUCCESS,
            )
            standard_checks = await client.filters(kind=CoreStandardCheck, validator__ids=validator.id)
            assert [(check.name.value, check.conclusion.value) for check in standard_checks] == [
                (IMPORT_STATUS_CHECK_NAME, ValidatorConclusion.SUCCESS.value)
            ]
            assert await client.filters(kind=CoreFileCheck, validator__ids=validator.id) == []

        proposed_change.state.value = ProposedChangeState.MERGED.value
        await proposed_change.save()

        proposed_change_after = await client.get(kind=CoreProposedChange, id=proposed_change.id)
        assert proposed_change_after.state.value == ProposedChangeState.MERGED.value

    async def test_branch_merge_waits_for_a_completed_import(
        self, repository_ids: dict[str, str], client: InfrahubClient
    ) -> None:
        """A branch with no completed import is refused, and merges once each import completes."""
        await client.branch.create(branch_name=INCOMPLETE_BRANCH_NAME, sync_with_git=False)
        await self._set_sync_status(
            client=client,
            repository_id=repository_ids[MANAGED_REPOSITORY],
            branch=INCOMPLETE_BRANCH_NAME,
            status=RepositorySyncStatus.SYNCING,
        )
        await self._set_sync_status(
            client=client,
            repository_id=repository_ids[READ_ONLY_REPOSITORY],
            branch=INCOMPLETE_BRANCH_NAME,
            status=RepositorySyncStatus.UNKNOWN,
        )

        with pytest.raises(GraphQLError) as excinfo:
            await client.branch.merge(branch_name=INCOMPLETE_BRANCH_NAME)

        assert [error["message"] for error in excinfo.value.errors] == [
            f"Cannot merge. Repositories '{MANAGED_REPOSITORY}', '{READ_ONLY_REPOSITORY}' have not finished "
            f"importing: wait for the import, or reimport the current commit if it does not finish."
        ]
        branch = await client.branch.get(branch_name=INCOMPLETE_BRANCH_NAME)
        assert branch.status == BranchStatus.OPEN

        for repository_id in repository_ids.values():
            await self._set_sync_status(
                client=client,
                repository_id=repository_id,
                branch=INCOMPLETE_BRANCH_NAME,
                status=RepositorySyncStatus.IN_SYNC,
            )
        await client.branch.merge(branch_name=INCOMPLETE_BRANCH_NAME)

        branch = await client.branch.get(branch_name=INCOMPLETE_BRANCH_NAME)
        assert branch.status == BranchStatus.MERGED
