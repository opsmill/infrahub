from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from unittest.mock import call, patch

import pytest

from infrahub.auth.session import AccountSession
from infrahub.auth.types import AuthType
from infrahub.context import BranchContext, InfrahubContext
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreReadOnlyRepository
from infrahub.git.divergence.suppression import RetargetMarkers
from infrahub.git.models import (
    GitReadOnlyRepositoryImportCommit,
    GitRepositoryImportObjects,
    GitRepositoryPullReadOnly,
)
from infrahub.graphql.mutations.repository import cleanup_payload
from infrahub.services import InfrahubServices
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.workflows.catalogue import (
    GIT_READ_ONLY_REPOSITORY_IMPORT_LAST_COMMIT,
    GIT_REPOSITORIES_IMPORT_OBJECTS,
    GIT_REPOSITORIES_PULL_READ_ONLY,
)
from tests.adapters.cache import MemoryCache
from tests.adapters.message_bus import BusRecorder
from tests.adapters.workflow import WorkflowRecorder
from tests.helpers.graphql import graphql_mutation

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase
    from infrahub.events.models import EventContext
    from infrahub.workflows.constants import WorkflowPriority
    from infrahub.workflows.models import WorkflowDefinition, WorkflowInfo


async def test_trigger_repository_import(
    db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch, create_test_admin: Node
) -> None:
    repository_model = registry.schema.get_node_schema(name=InfrahubKind.REPOSITORY, branch=default_branch)
    recorder = BusRecorder()
    service = await InfrahubServices.new(database=db, message_bus=recorder, workflow=WorkflowLocalExecution())
    account_session = AccountSession(
        authenticated=True, account_id=create_test_admin.id, session_id=None, auth_type=AuthType.API
    )
    # TODO: Removing this mock triggers issue: `Invalid file system for test-edge-demo, local directory ... missing`
    with (
        patch(
            "infrahub.services.adapters.workflow.local.WorkflowLocalExecution.submit_workflow"
        ) as mock_submit_workflow,
    ):
        RUN_REIMPORT = """
        mutation InfrahubRepositoryProcess($id: String!) {
            InfrahubRepositoryProcess(data: {id: $id}) {
                ok
            }
        }
        """

        repo = await Node.init(schema=repository_model, db=db, branch=default_branch)
        commit_id = "d85571671cf51f561fb0695d8657747f9ce84057"
        await repo.new(db=db, name="test-edge-demo", location="/tmp/edge", commit=commit_id)
        await repo.save(db=db)
        result = await graphql_mutation(
            query=RUN_REIMPORT, db=db, variables={"id": repo.id}, service=service, account_session=account_session
        )

        assert not result.errors
        assert result.data
        context = InfrahubContext(
            branch=BranchContext(name=default_branch.name, id=str(default_branch.get_uuid())),
            account=AccountSession(
                authenticated=True, account_id=create_test_admin.id, session_id=None, auth_type=AuthType.API
            ),
        )
        expected_calls = [
            call(
                workflow=GIT_REPOSITORIES_IMPORT_OBJECTS,
                parameters={
                    "model": GitRepositoryImportObjects(
                        repository_id=repo.id,
                        repository_name=str(repo.name.value),
                        repository_kind=repo.get_kind(),
                        commit=commit_id,
                        infrahub_branch_name=default_branch.name,
                    )
                },
                context=context,
            ),
        ]
        mock_submit_workflow.assert_has_calls(expected_calls)


async def test_repository_update(
    db: InfrahubDatabase, register_core_models_schema: None, default_branch: Branch
) -> None:
    branch2 = await create_branch(branch_name="branch2", db=db)
    repository_model = registry.schema.get_node_schema(name=InfrahubKind.REPOSITORY, branch=default_branch)
    recorder = BusRecorder()
    service = await InfrahubServices.new(database=db, message_bus=recorder)

    UPDATE_COMMIT = """
    mutation CoreRepositoryUpdate($id: String!, $commit_id: String!, $internal_status: String!) {
        CoreRepositoryUpdate(
            data: {
                id: $id
                commit: { value: $commit_id }
                internal_status: { value: $internal_status }
            }) {
            ok
        }
    }
    """
    commit_id = "d85571671cf51f561fb0695d8657747f9ce84057"

    # Create the repo in main
    repo = await Node.init(schema=repository_model, db=db, branch=branch2)
    await repo.new(db=db, name="test-edge-demo", location="/tmp/edge")
    await repo.save(db=db)

    repo.internal_status.value = RepositoryInternalStatus.STAGING.value
    await repo.save(db=db)

    result = await graphql_mutation(
        query=UPDATE_COMMIT,
        db=db,
        variables={"id": repo.id, "commit_id": commit_id, "internal_status": RepositoryInternalStatus.ACTIVE.value},
        service=service,
    )

    assert not result.errors
    assert result.data

    repo_main = await NodeManager.get_one(db=db, id=repo.id, raise_on_error=True)

    assert repo_main.internal_status.value == RepositoryInternalStatus.ACTIVE.value
    assert repo_main.commit.value == commit_id


@pytest.mark.parametrize(
    "test_input,expected",
    [
        ({"location": {"value": "/tmp/repo_dir"}}, {"location": {"value": "/tmp/repo_dir"}}),
        (
            {"location": {"value": "https://github.com/opsmill/infrahub-demo-edge-develop"}},
            {"location": {"value": "https://github.com/opsmill/infrahub-demo-edge-develop.git"}},
        ),
        (
            {"name": "demo", "location": {"value": "http://github.com/opsmill/infrahub-demo-edge-develop"}},
            {"name": "demo", "location": {"value": "http://github.com/opsmill/infrahub-demo-edge-develop.git"}},
        ),
        (
            {"name": "demo", "location": {"value": "http://gitlab.com/opsmill/infrahub-demo-edge-develop"}},
            {"name": "demo", "location": {"value": "http://gitlab.com/opsmill/infrahub-demo-edge-develop.git"}},
        ),
        (
            {"name": "demo", "location": {"value": "http://example.com/opsmill/infrahub-demo-edge-develop"}},
            {"name": "demo", "location": {"value": "http://example.com/opsmill/infrahub-demo-edge-develop"}},
        ),
        (
            {"name": "demo"},
            {"name": "demo"},
        ),
        (
            {"name": "demo", "location": {"value": "http://github.com/opsmill/infrahub-demo-edge-develop.git"}},
            {"name": "demo", "location": {"value": "http://github.com/opsmill/infrahub-demo-edge-develop.git"}},
        ),
    ],
)
def test_cleanup_payload(test_input: dict[str, Any], expected: dict[str, Any]) -> None:
    cleanup_payload(data=test_input)
    assert test_input == expected


async def test_import_last_commit_rejects_non_read_only_repository(
    db: InfrahubDatabase,
    register_core_models_schema: None,
    default_branch: Branch,
    create_test_admin: Node,
    default_permission_backend: None,
) -> None:
    """Calling InfrahubReadOnlyRepositoryImportLastCommit on a CoreRepository must fail.

    with a clear error instead of an AttributeError on the missing 'ref' attribute.

    """
    repository_model = registry.schema.get_node_schema(name=InfrahubKind.REPOSITORY, branch=default_branch)
    recorder = BusRecorder()
    service = await InfrahubServices.new(database=db, message_bus=recorder, workflow=WorkflowLocalExecution())
    account_session = AccountSession(
        authenticated=True, account_id=create_test_admin.id, session_id=None, auth_type=AuthType.API
    )

    IMPORT_LAST_COMMIT = """
    mutation InfrahubReadOnlyRepositoryImportLastCommit($id: String!) {
        InfrahubReadOnlyRepositoryImportLastCommit(
            data: {
                id: $id
            }) {
            ok
        }
    }
    """

    repo = await Node.init(schema=repository_model, db=db, branch=default_branch)
    await repo.new(db=db, name="test-regular-repo", location="/tmp/regular-repo")
    await repo.save(db=db)

    result = await graphql_mutation(
        query=IMPORT_LAST_COMMIT,
        db=db,
        variables={"id": repo.id},
        service=service,
        account_session=account_session,
    )

    assert result.errors
    assert "not a CoreReadOnlyRepository" in str(result.errors[0].message)


async def test_import_read_only_repository_last_commit(
    db: InfrahubDatabase,
    register_core_models_schema: None,
    default_branch: Branch,
    create_test_admin: Node,
    default_permission_backend: None,
) -> None:
    repository_model = registry.schema.get_node_schema(name=InfrahubKind.READONLYREPOSITORY, branch=default_branch)
    recorder = BusRecorder()
    service = await InfrahubServices.new(database=db, message_bus=recorder, workflow=WorkflowLocalExecution())
    account_session = AccountSession(
        authenticated=True, account_id=create_test_admin.id, session_id=None, auth_type=AuthType.API
    )

    with patch(
        "infrahub.services.adapters.workflow.local.WorkflowLocalExecution.submit_workflow"
    ) as mock_submit_workflow:
        IMPORT_LAST_COMMIT = """
        mutation InfrahubReadOnlyRepositoryImportLastCommit($id: String!) {
            InfrahubReadOnlyRepositoryImportLastCommit(
                data: {
                    id: $id
                }) {
                ok
            }
        }
        """

        repo = await Node.init(schema=repository_model, db=db, branch=default_branch)
        commit_id = "d85571671cf51f561fb0695d8657747f9ce84057"
        await repo.new(db=db, name="test-read-only-repo", location="/tmp/repo", ref="main", commit=commit_id)
        await repo.save(db=db)

        result = await graphql_mutation(
            query=IMPORT_LAST_COMMIT,
            db=db,
            variables={"id": repo.id},
            service=service,
            account_session=account_session,
        )

        assert not result.errors
        assert result.data

        expected_calls = [
            call(
                workflow=GIT_READ_ONLY_REPOSITORY_IMPORT_LAST_COMMIT,
                parameters={
                    "model": GitReadOnlyRepositoryImportCommit(
                        repository_id=repo.id,
                        repository_name=str(repo.name.value),
                        repository_kind=repo.get_kind(),
                        infrahub_branch_name=default_branch.name,
                        ref="main",
                    )
                },
                context=mock_submit_workflow.call_args.kwargs["context"],
            ),
        ]
        mock_submit_workflow.assert_has_calls(expected_calls)


PINNED_COMMIT = "d85571671cf51f561fb0695d8657747f9ce84057"
REPINNED_COMMIT = "0123456789abcdef0123456789abcdef01234567"


class CommittedTargetRecorder(WorkflowRecorder):
    """Records the ref and commit that another session reads for the repository at each submission."""

    def __init__(self, db: InfrahubDatabase, repository_id: str) -> None:
        super().__init__()
        self.db = db
        self.repository_id = repository_id
        self.committed_targets: list[tuple[str, str | None]] = []

    async def submit_workflow(
        self,
        workflow: WorkflowDefinition,
        context: InfrahubContext | EventContext | None = None,
        parameters: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        priority: WorkflowPriority | None = None,
    ) -> WorkflowInfo:
        async with self.db.start_session(read_only=True) as session:
            stored = await NodeManager.get_one(
                db=session, id=self.repository_id, kind=CoreReadOnlyRepository, raise_on_error=True
            )
        self.committed_targets.append((stored.ref.value, stored.commit.value))
        return await super().submit_workflow(
            workflow=workflow, context=context, parameters=parameters, tags=tags, priority=priority
        )


@dataclass
class ReadOnlyRepointTestCase:
    name: str
    mutation: str
    data: str
    """The mutation input that finds the repository and re-points it, in GraphQL input syntax."""
    expected_ref: str
    expected_commit: str | None
    committed_commit: str | None
    """The commit the database holds once the update commits."""


READ_ONLY_REPOINT_TEST_CASES: list[ReadOnlyRepointTestCase] = [
    ReadOnlyRepointTestCase(
        name="update_ref_changed",
        mutation="CoreReadOnlyRepositoryUpdate",
        data='id: "{repository_id}", ref: {{ value: "release" }}',
        expected_ref="release",
        expected_commit=None,
        committed_commit=PINNED_COMMIT,
    ),
    ReadOnlyRepointTestCase(
        name="update_only_the_commit_changed",
        mutation="CoreReadOnlyRepositoryUpdate",
        data=f'id: "{{repository_id}}", commit: {{{{ value: "{REPINNED_COMMIT}" }}}}',
        expected_ref="main",
        expected_commit=REPINNED_COMMIT,
        committed_commit=REPINNED_COMMIT,
    ),
    ReadOnlyRepointTestCase(
        name="update_the_pinned_commit_cleared",
        mutation="CoreReadOnlyRepositoryUpdate",
        data='id: "{repository_id}", commit: {{ value: null }}',
        expected_ref="main",
        expected_commit=None,
        committed_commit=None,
    ),
    ReadOnlyRepointTestCase(
        name="upsert_by_id_ref_changed",
        mutation="CoreReadOnlyRepositoryUpsert",
        data='id: "{repository_id}", ref: {{ value: "release" }}',
        expected_ref="release",
        expected_commit=None,
        committed_commit=PINNED_COMMIT,
    ),
    ReadOnlyRepointTestCase(
        name="upsert_by_hfid_only_the_commit_changed",
        mutation="CoreReadOnlyRepositoryUpsert",
        data=(
            'hfid: ["re-pointed-repo"], name: {{ value: "re-pointed-repo" }}, '
            'location: {{ value: "/tmp/re-pointed-repo" }}, ref: {{ value: "main" }}, '
            f'commit: {{{{ value: "{REPINNED_COMMIT}" }}}}'
        ),
        expected_ref="main",
        expected_commit=REPINNED_COMMIT,
        committed_commit=REPINNED_COMMIT,
    ),
    ReadOnlyRepointTestCase(
        name="upsert_by_name_ref_changed",
        mutation="CoreReadOnlyRepositoryUpsert",
        data=(
            'name: {{ value: "re-pointed-repo" }}, location: {{ value: "/tmp/re-pointed-repo" }}, '
            'ref: {{ value: "release" }}'
        ),
        expected_ref="release",
        expected_commit=None,
        committed_commit=PINNED_COMMIT,
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in READ_ONLY_REPOINT_TEST_CASES])
async def test_a_read_only_re_point_flags_both_workflows_after_the_commit_and_writes_no_marker(
    db: InfrahubDatabase,
    register_core_models_schema: None,
    default_branch: Branch,
    create_test_admin: Node,
    default_permission_backend: None,
    test_case: ReadOnlyRepointTestCase,
) -> None:
    """A workflow submitted before the commit still runs when the transaction rolls back."""
    cache = MemoryCache()
    account_session = AccountSession(
        authenticated=True, account_id=create_test_admin.id, session_id=None, auth_type=AuthType.API
    )
    repository_model = registry.schema.get_node_schema(name=InfrahubKind.READONLYREPOSITORY, branch=default_branch)
    repo = await Node.init(schema=repository_model, db=db, branch=default_branch)
    await repo.new(db=db, name="re-pointed-repo", location="/tmp/re-pointed-repo", ref="main", commit=PINNED_COMMIT)
    await repo.save(db=db)
    workflow = CommittedTargetRecorder(db=db, repository_id=repo.id)
    service = await InfrahubServices.new(database=db, cache=cache, workflow=workflow)

    result = await graphql_mutation(
        query=(
            f"mutation {{ {test_case.mutation}(data: {{ {test_case.data.format(repository_id=repo.id)} }}) {{ ok }} }}"
        ),
        db=db,
        service=service,
        account_session=account_session,
    )

    assert result.errors is None
    assert [(call["workflow"], call["parameters"]) for call in workflow.submit_calls] == [
        (
            GIT_REPOSITORIES_PULL_READ_ONLY,
            {
                "model": GitRepositoryPullReadOnly(
                    repository_id=repo.id,
                    repository_name="re-pointed-repo",
                    location="/tmp/re-pointed-repo",
                    ref=test_case.expected_ref,
                    commit=test_case.expected_commit,
                    infrahub_branch_name=default_branch.name,
                    infrahub_branch_id=str(default_branch.get_uuid()),
                    target_changed=True,
                )
            },
        ),
        (
            GIT_READ_ONLY_REPOSITORY_IMPORT_LAST_COMMIT,
            {
                "model": GitReadOnlyRepositoryImportCommit(
                    repository_id=repo.id,
                    repository_name="re-pointed-repo",
                    repository_kind=InfrahubKind.READONLYREPOSITORY,
                    infrahub_branch_name=default_branch.name,
                    ref=test_case.expected_ref,
                    target_changed=True,
                )
            },
        ),
    ]
    committed_target = (test_case.expected_ref, test_case.committed_commit)
    assert workflow.committed_targets == [committed_target, committed_target]
    assert cache.storage == {}


@dataclass
class ReadOnlyKeptTargetTestCase:
    name: str
    mutation: str
    data: str
    """The mutation input that finds the repository and repeats its ref and commit, in GraphQL input syntax."""


READ_ONLY_KEPT_TARGET_TEST_CASES: list[ReadOnlyKeptTargetTestCase] = [
    ReadOnlyKeptTargetTestCase(
        name="update",
        mutation="CoreReadOnlyRepositoryUpdate",
        data=(
            'id: "{repository_id}", description: {{ value: "described" }}, ref: {{ value: "main" }}, '
            f'commit: {{{{ value: "{PINNED_COMMIT}" }}}}'
        ),
    ),
    ReadOnlyKeptTargetTestCase(
        name="upsert_by_hfid",
        mutation="CoreReadOnlyRepositoryUpsert",
        data=(
            'hfid: ["kept-repo"], name: {{ value: "kept-repo" }}, location: {{ value: "/tmp/kept-repo" }}, '
            'description: {{ value: "described" }}, ref: {{ value: "main" }}, '
            f'commit: {{{{ value: "{PINNED_COMMIT}" }}}}'
        ),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in READ_ONLY_KEPT_TARGET_TEST_CASES])
async def test_a_read_only_edit_that_keeps_the_ref_and_commit_submits_no_workflow(
    db: InfrahubDatabase,
    register_core_models_schema: None,
    default_branch: Branch,
    create_test_admin: Node,
    default_permission_backend: None,
    test_case: ReadOnlyKeptTargetTestCase,
) -> None:
    workflow = WorkflowRecorder()
    service = await InfrahubServices.new(database=db, cache=MemoryCache(), workflow=workflow)
    account_session = AccountSession(
        authenticated=True, account_id=create_test_admin.id, session_id=None, auth_type=AuthType.API
    )
    repository_model = registry.schema.get_node_schema(name=InfrahubKind.READONLYREPOSITORY, branch=default_branch)
    repo = await Node.init(schema=repository_model, db=db, branch=default_branch)
    await repo.new(db=db, name="kept-repo", location="/tmp/kept-repo", ref="main", commit=PINNED_COMMIT)
    await repo.save(db=db)

    result = await graphql_mutation(
        query=(
            f"mutation {{ {test_case.mutation}(data: {{ {test_case.data.format(repository_id=repo.id)} }}) {{ ok }} }}"
        ),
        db=db,
        service=service,
        account_session=account_session,
    )

    assert result.errors is None
    edited = await NodeManager.get_one(db=db, id=repo.id, kind=CoreReadOnlyRepository, raise_on_error=True)
    assert (edited.description.value, edited.ref.value, edited.commit.value) == ("described", "main", PINNED_COMMIT)
    assert workflow.submit_calls == []


@dataclass
class DefaultBranchEditTestCase:
    name: str
    infrahub_branch_name: str
    """The Infrahub branch the update runs on."""


DEFAULT_BRANCH_EDIT_TEST_CASES: list[DefaultBranchEditTestCase] = [
    DefaultBranchEditTestCase(name="edit_on_the_default_branch", infrahub_branch_name="main"),
    DefaultBranchEditTestCase(name="edit_on_another_branch", infrahub_branch_name="branch2"),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in DEFAULT_BRANCH_EDIT_TEST_CASES])
async def test_a_default_branch_edit_marks_the_infrahub_default_branch_for_the_next_sync(
    db: InfrahubDatabase,
    register_core_models_schema: None,
    default_branch: Branch,
    create_test_admin: Node,
    default_permission_backend: None,
    test_case: DefaultBranchEditTestCase,
) -> None:
    """The repository is agnostic to branches, so the edit moves what feeds the default branch wherever it runs."""
    branch = await create_branch(branch_name="branch2", db=db)
    cache = MemoryCache()
    workflow = WorkflowRecorder()
    service = await InfrahubServices.new(database=db, cache=cache, workflow=workflow)
    account_session = AccountSession(
        authenticated=True, account_id=create_test_admin.id, session_id=None, auth_type=AuthType.API
    )
    repository_model = registry.schema.get_node_schema(name=InfrahubKind.REPOSITORY, branch=default_branch)
    repo = await Node.init(schema=repository_model, db=db, branch=default_branch)
    await repo.new(db=db, name="re-pointed-repo", location="/tmp/re-pointed-repo", default_branch="main")
    await repo.save(db=db)

    result = await graphql_mutation(
        query=f'mutation {{ CoreRepositoryUpdate(data: {{ id: "{repo.id}", default_branch: {{ value: "release" }} }}) {{ ok }} }}',
        db=db,
        service=service,
        branch=default_branch if test_case.infrahub_branch_name == "main" else branch,
        account_session=account_session,
    )

    assert result.errors is None
    markers = RetargetMarkers(cache=cache)
    assert await markers.is_retargeted(repository_id=repo.id, target="release")
    assert list(cache.storage.values()) == ["release"]
    assert workflow.submit_calls == []


@dataclass
class DefaultBranchUpsertTestCase:
    name: str
    data: str
    """The upsert input that finds the repository and changes its default branch."""


DEFAULT_BRANCH_UPSERT_TEST_CASES: list[DefaultBranchUpsertTestCase] = [
    DefaultBranchUpsertTestCase(
        name="upsert_by_id",
        data='id: "{repository_id}", default_branch: {{ value: "release" }}',
    ),
    DefaultBranchUpsertTestCase(
        name="upsert_by_name",
        data=(
            'name: {{ value: "upserted-repo" }}, location: {{ value: "/tmp/upserted-repo" }}, '
            'default_branch: {{ value: "release" }}'
        ),
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in DEFAULT_BRANCH_UPSERT_TEST_CASES])
async def test_an_upsert_that_changes_the_default_branch_marks_the_infrahub_default_branch(
    db: InfrahubDatabase,
    register_core_models_schema: None,
    default_branch: Branch,
    create_test_admin: Node,
    default_permission_backend: None,
    test_case: DefaultBranchUpsertTestCase,
) -> None:
    cache = MemoryCache()
    service = await InfrahubServices.new(database=db, cache=cache, workflow=WorkflowRecorder())
    account_session = AccountSession(
        authenticated=True, account_id=create_test_admin.id, session_id=None, auth_type=AuthType.API
    )
    repository_model = registry.schema.get_node_schema(name=InfrahubKind.REPOSITORY, branch=default_branch)
    repo = await Node.init(schema=repository_model, db=db, branch=default_branch)
    await repo.new(db=db, name="upserted-repo", location="/tmp/upserted-repo", default_branch="main")
    await repo.save(db=db)

    result = await graphql_mutation(
        query=f"mutation {{ CoreRepositoryUpsert(data: {{ {test_case.data.format(repository_id=repo.id)} }}) {{ ok }} }}",
        db=db,
        service=service,
        account_session=account_session,
    )

    assert result.errors is None
    upserted = await NodeManager.get_one(db=db, id=repo.id, raise_on_error=True)
    assert upserted.get_attribute("default_branch").value == "release"
    assert await RetargetMarkers(cache=cache).is_retargeted(repository_id=repo.id, target="release")
    assert list(cache.storage.values()) == ["release"]


async def test_an_edit_that_keeps_the_default_branch_writes_no_marker(
    db: InfrahubDatabase,
    register_core_models_schema: None,
    default_branch: Branch,
    create_test_admin: Node,
    default_permission_backend: None,
) -> None:
    cache = MemoryCache()
    service = await InfrahubServices.new(database=db, cache=cache, workflow=WorkflowRecorder())
    account_session = AccountSession(
        authenticated=True, account_id=create_test_admin.id, session_id=None, auth_type=AuthType.API
    )
    repository_model = registry.schema.get_node_schema(name=InfrahubKind.REPOSITORY, branch=default_branch)
    repo = await Node.init(schema=repository_model, db=db, branch=default_branch)
    await repo.new(db=db, name="described-repo", location="/tmp/described-repo", default_branch="main")
    await repo.save(db=db)

    result = await graphql_mutation(
        query=(
            f'mutation {{ CoreRepositoryUpdate(data: {{ id: "{repo.id}", description: {{ value: "described" }}, '
            'default_branch: { value: "main" } }) { ok } }'
        ),
        db=db,
        service=service,
        account_session=account_session,
    )

    assert result.errors is None
    assert cache.storage == {}
