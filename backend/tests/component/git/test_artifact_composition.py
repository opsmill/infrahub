from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from git import Repo
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.uuidt import UUIDT

from infrahub.core.constants import InfrahubKind
from infrahub.exceptions import TransformError
from infrahub.services import InfrahubServices
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.transformations.models import TransformJinjaTemplateData
from infrahub.transformations.tasks import transform_render_jinja2_template
from infrahub.workers.dependencies import build_client
from tests.helpers.git import build_repository_client, clone_repository
from tests.helpers.test_client import dummy_async_request

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from fast_depends import Provider

    from infrahub.git import InfrahubRepository


@pytest.fixture
async def init_service() -> InfrahubServices:
    return await InfrahubServices.new(client=InfrahubClient(), workflow=WorkflowLocalExecution())


@pytest.fixture
async def git_repo_filter_tests(git_upstream_repo_02: dict[str, str | Path], git_repos_dir: Path) -> InfrahubRepository:
    upstream = Repo(git_upstream_repo_02["path"])

    templates = {
        # Untrusted filter
        "template_untrusted.tpl.j2": '{% for item in data["items"] %}{{ item | fqdn_to_ip }}\n{% endfor %}\n',
        # Trusted filter
        "template_trusted.tpl.j2": '{% for item in data["items"] %}{{ item | upper }}\n{% endfor %}\n',
    }

    for name, content in templates.items():
        (git_upstream_repo_02["path"] / name).write_text(content, encoding="utf-8")
        upstream.index.add(name)

    upstream.index.commit("Add filter test templates")

    return await clone_repository(
        id=UUIDT.new(),
        name=git_upstream_repo_02["name"],
        location=str(git_upstream_repo_02["path"]),
        client=InfrahubClient(config=Config(requester=dummy_async_request)),
    )


def _make_message(repo: InfrahubRepository, template: str) -> TransformJinjaTemplateData:
    """Craft a message to test the transform flow."""
    return TransformJinjaTemplateData(
        repository_id=str(repo.id),
        repository_name=repo.name,
        repository_kind=InfrahubKind.REPOSITORY,
        commit=repo.get_commit_value(branch_name="main"),
        branch="main",
        template_location=template,
        timeout=10,
        data={"items": ["one", "two"]},
    )


@pytest.fixture
def worker_client(
    dependency_provider: Provider,
    register_core_models_schema: None,
    git_repo_filter_tests: InfrahubRepository,
) -> Generator[None, None, None]:
    """Serve the repository read the transform flow's own construction performs."""
    client = build_repository_client(
        repository_id=str(git_repo_filter_tests.id),
        name=git_repo_filter_tests.name,
        location=git_repo_filter_tests.get_location(),
        default_branch="main",
    )
    with dependency_provider.scope(build_client, lambda: client):
        yield


async def test_worker_rejects_local_only_filter(
    git_repo_filter_tests: InfrahubRepository,
    init_service: InfrahubServices,
    prefect_test_fixture: None,
    worker_client: None,
) -> None:
    with pytest.raises(TransformError, match="'fqdn_to_ip' filter isn't allowed to be used"):
        await transform_render_jinja2_template(
            message=_make_message(git_repo_filter_tests, "template_untrusted.tpl.j2")
        )


async def test_worker_allows_trusted_filters(
    git_repo_filter_tests: InfrahubRepository,
    init_service: InfrahubServices,
    prefect_test_fixture: None,
    worker_client: None,
) -> None:
    result = await transform_render_jinja2_template(
        message=_make_message(git_repo_filter_tests, "template_trusted.tpl.j2")
    )
    assert result == "ONE\nTWO\n"
