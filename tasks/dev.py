from __future__ import annotations

import os
from typing import TYPE_CHECKING

from invoke.tasks import task

from .container_ops import (
    build_images,
    destroy_environment,
    display_container_status,
    pull_images,
    restart_services,
    show_service_status,
    start_services,
    stop_services,
    upgrade_infrahub,
)
from .infra_ops import load_infrastructure_data, load_infrastructure_menu, load_infrastructure_schema
from .shared import (
    BUILD_NAME,
    INFRAHUB_DATABASE,
    PYTHON_VER,
    SERVICE_WORKER_NAME,
    Namespace,
    build_compose_files_cmd,
    build_dev_compose_files_cmd,
    execute_command,
    get_compose_cmd,
    get_env_vars,
)
from .utils import ESCAPED_REPO_PATH, check_if_command_available

if TYPE_CHECKING:
    from invoke.context import Context

NAMESPACE = Namespace.DEV


@task(optional=["database"])
def build(
    context: Context,
    service: str | None = None,
    python_ver: str = PYTHON_VER,
    nocache: bool = False,
    database: str = INFRAHUB_DATABASE,
) -> None:
    """Build an image with the provided name and python version.

    Args:
        context (obj): Used to run specific commands
        python_ver (str): Define the Python version docker image to build from
        nocache (bool): Do not use cache when building the image

    """
    build_images(
        context=context, service=service, python_ver=python_ver, nocache=nocache, database=database, namespace=NAMESPACE
    )


@task(optional=["database"])
def debug(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Start a local instance of Infrahub in debug mode."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database)
        compose_cmd = get_compose_cmd(namespace=NAMESPACE)
        command = f"{get_env_vars(context, namespace=NAMESPACE)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME} up"
        execute_command(context=context, command=command)


@task()
def check_links(
    context: Context,
) -> None:
    """Check internal links in the dev folder."""
    with context.cd(ESCAPED_REPO_PATH):
        if not check_if_command_available(context=context, command_name="lychee"):
            print("lychee is not installed or not available in PATH. Please install it to use this task.")
            return
        execute_command(context=context, command="lychee -c dev/lychee.toml --files-from dev/lychee-files.txt")


@task(optional=["database"])
def deps(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Start local instances of dependencies (Databases and Message Bus)."""
    with context.cd(ESCAPED_REPO_PATH):
        dev_compose_files_cmd = build_dev_compose_files_cmd(database=database)
        compose_cmd = get_compose_cmd(namespace=NAMESPACE)
        command = (
            f"{get_env_vars(context, namespace=NAMESPACE)} {compose_cmd} {dev_compose_files_cmd} -p {BUILD_NAME} up -d"
        )
        execute_command(context=context, command=command)


@task
def destroy(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Destroy all containers and volumes."""
    destroy_environment(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def infra_git_create(
    context: Context,
    database: str = INFRAHUB_DATABASE,
    name: str = "demo-edge",
    location: str = "/remote/infrahub-demo-edge",
) -> None:
    """Register a Git repository with Infrahub via docker compose."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=NAMESPACE)
        compose_cmd = get_compose_cmd(namespace=NAMESPACE)
        base_cmd = f"{get_env_vars(context, namespace=NAMESPACE)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"
        execute_command(
            context=context,
            command=f"{base_cmd} run {SERVICE_WORKER_NAME} infrahubctl repository add {name} {location}",
        )


@task(optional=["database"])
def infra_git_import(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Initialize a demo Git repository inside the worker container."""
    REPO_NAME = "infrahub-demo-edge"
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=NAMESPACE)
        compose_cmd = get_compose_cmd(namespace=NAMESPACE)
        base_cmd = f"{get_env_vars(context, namespace=NAMESPACE)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"
        execute_command(
            context=context,
            command=f"{base_cmd} run {SERVICE_WORKER_NAME} cp -r backend/tests/fixtures/repos/{REPO_NAME}/initial__main /remote/{REPO_NAME}",
        )
        execute_command(
            context=context,
            command=f"{base_cmd} exec --workdir /remote/{REPO_NAME} {SERVICE_WORKER_NAME} git init --initial-branch main",
        )
        execute_command(
            context=context,
            command=f"{base_cmd} exec --workdir /remote/{REPO_NAME} {SERVICE_WORKER_NAME} git add .",
        )
        execute_command(
            context=context,
            command=f"{base_cmd} exec --workdir /remote/{REPO_NAME} {SERVICE_WORKER_NAME} git commit -m first",
        )


@task(optional=["database"])
def load_infra_data(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Load infrastructure demo data."""
    load_infrastructure_data(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def load_infra_schema(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Load the base schema for infrastructure."""
    load_infrastructure_schema(context=context, database=database, namespace=NAMESPACE, add_wait=True)
    load_infrastructure_menu(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def pull(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Pull external containers from registry."""
    pull_images(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def restart(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Restart Infrahub API Server and Task worker within docker compose."""
    restart_services(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def status(
    context: Context,
    database: str = INFRAHUB_DATABASE,
    watch: bool = False,
    interval: int = 2,
) -> None:
    """Display detailed status and metrics of all services."""
    try:
        display_container_status(
            context=context, database=database, namespace=NAMESPACE, watch=watch, interval=interval
        )
    except ImportError:
        show_service_status(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def start(context: Context, database: str = INFRAHUB_DATABASE, wait: bool = False, reload: bool = False) -> None:
    """Start a local instance of Infrahub within docker compose."""
    if reload:
        # Need to use `uvicorn` instead of `gunicorn` for reload option because of this issue:
        # https://github.com/benoitc/gunicorn/issues/2339
        os.environ["INFRAHUB_SERVER_COMMAND"] = (
            "uvicorn infrahub.server:app --host 0.0.0.0 --port 8000 --workers 4 --timeout-keep-alive 90 --reload"
        )

    start_services(context=context, database=database, namespace=NAMESPACE, wait=wait)


@task(optional=["database"])
def stop(context: Context, database: str = INFRAHUB_DATABASE) -> None:
    """Stop the running instance of Infrahub."""
    stop_services(context=context, database=database, namespace=NAMESPACE)


@task(optional=["database"])
def upgrade(context: Context, database: str = INFRAHUB_DATABASE, rebase_branches: bool = False) -> None:
    """Upgrade Infrahub to the latest version and apply the required migrations."""
    upgrade_infrahub(context=context, database=database, namespace=NAMESPACE, rebase_branches=rebase_branches)


@task
def test_add_dummy_data(context: Context, branch: str = "main") -> str:  # noqa: ARG001
    """Load dummy data for testing."""
    from infrahub_sdk import InfrahubClientSync
    from infrahub_sdk.uuidt import generate_uuid

    client = InfrahubClientSync()

    node_name = f"test_rebase_{generate_uuid()}"

    # Create dummy data in main
    test_data = client.create(kind="LocationContinent", data={"name": node_name}, branch=branch)
    test_data.save()

    print(node_name)

    return node_name


@task
def test_branch_rebase(context: Context, branch: str, data_to_check: str = "") -> None:  # noqa: ARG001
    """Rebase branch and check for schema and data.

    Raises:
        AssertionError: When the precondition fails or the expected schema is missing after rebase.

    """
    from infrahub_sdk import InfrahubClientSync
    from infrahub_sdk.exceptions import NodeNotFoundError
    from infrahub_sdk.task.models import TaskFilter
    from infrahub_sdk.uuidt import generate_uuid

    client = InfrahubClientSync()

    node_name = f"test_rebase_{generate_uuid()}"

    # Create dummy data in main
    test_data = client.create(kind="LocationContinent", data={"name": node_name}, branch="main")
    test_data.save()

    # Check that data is not present in branch
    try:
        client.get(kind="LocationContinent", hfid=node_name, branch=branch)
        raise AssertionError(
            f"Precondition failed: {node_name!r} unexpectedly exists on branch {branch!r} before rebase"
        )
    except NodeNotFoundError:
        pass

    client.branch.rebase(branch_name=branch)

    tasks = client.task.filter(filter=TaskFilter(workflow=["branch-rebase"]))
    for rebase_task in tasks:
        client.task.wait_for_completion(id=rebase_task.id)

    # Check schema
    schema_to_check = "LocationGeneric"
    full_schema = client.schema.all(branch=branch)
    if schema_to_check not in full_schema:
        raise AssertionError(f"Could not find {schema_to_check} in schema")

    # Check data
    client.get(kind="LocationContinent", hfid=node_name, branch=branch)

    if data_to_check:
        client.get(kind="LocationContinent", hfid=data_to_check, branch=branch)


def _init_git_repo_in_worker(context: Context, git_repo_path: str, database: str = INFRAHUB_DATABASE) -> None:
    """Initialise a bare git repo at *git_repo_path* inside the running task-worker container.

    The task-worker's ``/remote`` volume is used as the working area.  The repo is seeded
    from the demo-edge fixture tree that is always present in the container at
    ``/source/backend/tests/fixtures/repos/infrahub-demo-edge/initial__main``.

    Every step runs through the shared compose abstractions (``get_compose_cmd`` /
    ``build_compose_files_cmd`` / ``execute_command``) so the helper honours the same
    profiles, ``--ansi`` handling and ``sudo`` wrapping as the rest of the dev tasks.
    We use ``docker compose exec`` against the already-running worker — never ``run``,
    which would start the service's ``depends_on`` dependencies and recreate the
    server container on a fresh random port, breaking the SDK connection used by the
    calling task.
    """
    fixture_path = "/source/backend/tests/fixtures/repos/infrahub-demo-edge/initial__main"
    git_ci_opts = "-c user.email=ci@test.invalid -c user.name=CI"
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=NAMESPACE)
        compose_cmd = get_compose_cmd(namespace=NAMESPACE)
        base_cmd = f"{get_env_vars(context, namespace=NAMESPACE)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"
        worker_exec = f"{base_cmd} exec --workdir {git_repo_path} {SERVICE_WORKER_NAME}"
        # hide=True keeps the git/docker chatter off stdout: the calling task prints
        # only the repo id, which the version-upgrade workflow captures via `$(...)`.
        execute_command(
            context=context,
            command=f"{base_cmd} exec {SERVICE_WORKER_NAME} cp -r {fixture_path} {git_repo_path}",
            hide=True,
        )
        execute_command(context=context, command=f"{worker_exec} git init --initial-branch main", hide=True)
        execute_command(context=context, command=f"{worker_exec} git add .", hide=True)
        execute_command(context=context, command=f"{worker_exec} git {git_ci_opts} commit -m initial", hide=True)


@task
def test_add_repository_cascade_data(context: Context, branch: str = "main") -> str:
    """Create a CoreReadOnlyRepository and one of every managed object linked to it.

    Used by the version-upgrade CI job to prove cascade-delete still works after
    a schema migration (the on_delete=CASCADE value is only persisted after upgrade).

    Returns:
        str: The repository node id, printed to stdout for capture by the workflow.

    Raises:
        RuntimeError: When no InfraDevice nodes are found (demo.load-infra-data must run first).

    """
    from infrahub_sdk import InfrahubClientSync
    from infrahub_sdk.uuidt import generate_uuid

    client = InfrahubClientSync()

    suffix = generate_uuid()[:8]

    # Create the repository under test.
    # Initialise a throw-away bare git repo inside the task-worker container so the
    # connectivity check passes without needing an external network connection.
    # Each invocation uses a fresh directory name (via suffix) to avoid location uniqueness conflicts.
    git_repo_path = f"/remote/cascade-test-{suffix}"
    _init_git_repo_in_worker(context, git_repo_path)

    repo = client.create(
        kind="CoreReadOnlyRepository",
        data={
            "name": f"cascade-test-repo-{suffix}",
            "location": f"file://{git_repo_path}",
        },
        branch=branch,
    )
    repo.save()

    # GraphQL query linked to the repository
    gql_query = client.create(
        kind="CoreGraphQLQuery",
        data={
            "name": f"cascade-test-query-{suffix}",
            "query": "{ CoreReadOnlyRepository { edges { node { id } } } }",
            "repository": {"id": repo.id},
        },
        branch=branch,
    )
    gql_query.save()

    # GraphQL query group referencing the query
    query_group = client.create(
        kind="CoreGraphQLQueryGroup",
        data={
            "name": f"cascade-test-qgroup-{suffix}",
            "query": {"id": gql_query.id},
        },
        branch=branch,
    )
    query_group.save()

    # Standard group used as targets for artifact/generator definitions
    group = client.create(
        kind="CoreStandardGroup",
        data={"name": f"cascade-test-group-{suffix}"},
        branch=branch,
    )
    group.save()

    # Python transform linked to the repository and query
    transform = client.create(
        kind="CoreTransformPython",
        data={
            "name": f"cascade-test-transform-{suffix}",
            "repository": {"id": repo.id},
            "query": {"id": gql_query.id},
            "file_path": "transform.py",
            "class_name": "CascadeTransform",
        },
        branch=branch,
    )
    transform.save()

    # Artifact definition referencing the transform and targeting the group
    artifact_def = client.create(
        kind="CoreArtifactDefinition",
        data={
            "name": f"cascade-test-artifactdef-{suffix}",
            "transformation": {"id": transform.id},
            "targets": {"id": group.id},
            "artifact_name": f"cascade-artifact-{suffix}",
            "content_type": "application/json",
            "parameters": {"value": {"name": "name__value"}},
        },
        branch=branch,
    )
    artifact_def.save()

    # Fetch an InfraDevice node (created by load-infra-data) to use as the Artifact object
    devices = client.all(kind="InfraDevice", branch=branch, limit=1)
    device_list = list(devices)
    if not device_list:
        raise RuntimeError("No InfraDevice found — ensure demo.load-infra-data ran before this task")
    artifact_target = device_list[0]

    # Artifact referencing the artifact definition and an ArtifactTarget object
    artifact = client.create(
        kind="CoreArtifact",
        data={
            "name": f"cascade-test-artifact-{suffix}",
            "definition": {"id": artifact_def.id},
            "object": {"id": artifact_target.id},
            "status": "Ready",
            "content_type": "application/json",
            "storage_id": f"00000000-0000-0000-0000-{suffix}",
            "checksum": f"abc{suffix}",
        },
        branch=branch,
    )
    artifact.save()

    # Check definition linked to the repository
    check_def = client.create(
        kind="CoreCheckDefinition",
        data={
            "name": f"cascade-test-checkdef-{suffix}",
            "repository": {"id": repo.id},
            "class_name": "CascadeCheck",
            "file_path": "check.py",
        },
        branch=branch,
    )
    check_def.save()

    # Generator definition linked to the repository
    generator_def = client.create(
        kind="CoreGeneratorDefinition",
        data={
            "name": f"cascade-test-generatordef-{suffix}",
            "repository": {"id": repo.id},
            "query": {"id": gql_query.id},
            "targets": {"id": group.id},
            "class_name": "CascadeGenerator",
            "file_path": "generator.py",
            "parameters": {"value": {"name": "name__value"}},
        },
        branch=branch,
    )
    generator_def.save()

    # Generator instance linked to the generator definition
    generator_instance = client.create(
        kind="CoreGeneratorInstance",
        data={
            "name": f"cascade-test-geninstance-{suffix}",
            "definition": {"id": generator_def.id},
            "object": {"id": artifact_target.id},
            "status": "Ready",
        },
        branch=branch,
    )
    generator_instance.save()

    # Repository group tracking the repository
    repo_group = client.create(
        kind="CoreRepositoryGroup",
        data={
            "name": f"cascade-test-repogroup-{suffix}",
            "repository": {"id": repo.id},
            "content": "object",
        },
        branch=branch,
    )
    repo_group.save()

    # Proposed change required for validators — source and destination must differ.
    # Create a throw-away source branch then propose merging it back into main.
    pc_branch_name = f"cascade-test-branch-{suffix}"
    client.branch.create(branch_name=pc_branch_name, sync_with_git=False)
    proposed_change = client.create(
        kind="CoreProposedChange",
        data={
            "name": f"cascade-test-pc-{suffix}",
            "source_branch": pc_branch_name,
            "destination_branch": "main",
        },
        branch="main",
    )
    proposed_change.save()

    # Artifact validator referencing the artifact definition and proposed change
    artifact_validator = client.create(
        kind="CoreArtifactValidator",
        data={
            "proposed_change": {"id": proposed_change.id},
            "definition": {"id": artifact_def.id},
        },
        branch="main",
    )
    artifact_validator.save()

    # Generator validator referencing the generator definition and proposed change
    generator_validator = client.create(
        kind="CoreGeneratorValidator",
        data={
            "proposed_change": {"id": proposed_change.id},
            "definition": {"id": generator_def.id},
        },
        branch="main",
    )
    generator_validator.save()

    # User validator referencing the check definition, repository and proposed change
    user_validator = client.create(
        kind="CoreUserValidator",
        data={
            "proposed_change": {"id": proposed_change.id},
            "check_definition": {"id": check_def.id},
            "repository": {"id": repo.id},
        },
        branch="main",
    )
    user_validator.save()

    print(repo.id)
    return repo.id


@task
def test_repository_cascade_delete(context: Context, repo_id: str) -> None:  # noqa: ARG001
    """Delete a repository by id and assert every descendant is also gone.

    Raises:
        AssertionError: When the repository or any descendant survives deletion.

    """
    from infrahub_sdk import InfrahubClientSync
    from infrahub_sdk.exceptions import NodeNotFoundError

    client = InfrahubClientSync()

    # Fetch the repository and collect descendant ids via its relationships
    repo = client.get(kind="CoreReadOnlyRepository", id=repo_id)

    descendant_ids: list[str] = []

    # Walk repository-owned relationships that should cascade
    for transform in repo.transformations.peers:  # type: ignore[attr-defined]
        descendant_ids.append(transform.id)
        # Artifact definitions owned by this transform, and their artifacts + validators
        for adef in client.filters(kind="CoreArtifactDefinition", transformation__ids=[transform.id]):
            descendant_ids.append(adef.id)
            descendant_ids.extend(art.id for art in client.filters(kind="CoreArtifact", definition__ids=[adef.id]))
            descendant_ids.extend(
                av.id for av in client.filters(kind="CoreArtifactValidator", definition__ids=[adef.id])
            )

    for qry in repo.queries.peers:  # type: ignore[attr-defined]
        descendant_ids.append(qry.id)
        descendant_ids.extend(qgrp.id for qgrp in client.filters(kind="CoreGraphQLQueryGroup", query__ids=[qry.id]))

    for chk in repo.checks.peers:  # type: ignore[attr-defined]
        descendant_ids.append(chk.id)
        descendant_ids.extend(uv.id for uv in client.filters(kind="CoreUserValidator", check_definition__ids=[chk.id]))

    for gen in repo.generators.peers:  # type: ignore[attr-defined]
        descendant_ids.append(gen.id)
        descendant_ids.extend(
            ginst.id for ginst in client.filters(kind="CoreGeneratorInstance", definition__ids=[gen.id])
        )
        descendant_ids.extend(gv.id for gv in client.filters(kind="CoreGeneratorValidator", definition__ids=[gen.id]))

    descendant_ids.extend(rgrp.id for rgrp in repo.groups_objects.peers)  # type: ignore[attr-defined]

    # Delete the repository
    client.delete(kind="CoreReadOnlyRepository", id=repo_id)

    # Verify the repository itself is gone
    missing_repo = False
    try:
        client.get(kind="CoreReadOnlyRepository", id=repo_id)
    except NodeNotFoundError:
        missing_repo = True
    if not missing_repo:
        raise AssertionError(f"Repository {repo_id!r} was NOT deleted")

    # Verify every tracked descendant is also gone by trying each known kind in order.
    # The first kind that returns the node is recorded as a survivor.
    all_descendant_kinds = [
        "CoreTransformPython",
        "CoreArtifactDefinition",
        "CoreArtifact",
        "CoreGraphQLQuery",
        "CoreGraphQLQueryGroup",
        "CoreCheckDefinition",
        "CoreGeneratorDefinition",
        "CoreGeneratorInstance",
        "CoreRepositoryGroup",
        "CoreArtifactValidator",
        "CoreGeneratorValidator",
        "CoreUserValidator",
    ]
    surviving: list[str] = []
    for desc_id in descendant_ids:
        for kind in all_descendant_kinds:
            try:
                client.get(kind=kind, id=desc_id)
                surviving.append(f"{kind}:{desc_id}")
                break
            except NodeNotFoundError:
                pass

    if surviving:
        raise AssertionError(
            f"Repository cascade-delete did NOT remove {len(surviving)} descendant(s):\n" + "\n".join(surviving)
        )

    print(f"OK: repository {repo_id!r} and {len(descendant_ids)} descendant(s) all deleted")


@task
def test_branch_graph_version(context: Context, branch: str) -> None:  # noqa: ARG001
    """Verify a branch has been rebased and upgraded with a valid graph version.

    Raises:
        AssertionError: When the branch has no graph version set.

    """
    from infrahub_sdk import InfrahubClientSync

    client = InfrahubClientSync()

    b = client.branch.get(branch_name=branch)
    if b.graph_version is None:
        raise AssertionError(
            f"Branch '{branch}' with graph version {b.graph_version} has not been rebased and upgrade properly"
        )
