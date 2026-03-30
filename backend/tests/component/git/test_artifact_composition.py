from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from git import Repo
from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.uuidt import UUIDT

from infrahub.core.constants import InfrahubKind
from infrahub.exceptions import TransformError
from infrahub.git import InfrahubRepository
from infrahub.services import InfrahubServices
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution
from infrahub.transformations.models import TransformJinjaTemplateData
from infrahub.transformations.tasks import transform_render_jinja2_template
from tests.helpers.test_client import dummy_async_request

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
async def init_service() -> InfrahubServices:
    return await InfrahubServices.new(client=InfrahubClient(), workflow=WorkflowLocalExecution())


@pytest.fixture
async def git_repo_filter_tests(git_upstream_repo_02: dict[str, str | Path], git_repos_dir: Path) -> InfrahubRepository:
    upstream = Repo(git_upstream_repo_02["path"])

    templates = {
        # Untrusted filter
        "template_safe.tpl.j2": '{% for item in data["items"] %}{{ item | safe }}\n{% endfor %}\n',
        # Trusted filter
        "template_upper.tpl.j2": '{% for item in data["items"] %}{{ item | upper }}\n{% endfor %}\n',
    }

    for name, content in templates.items():
        (git_upstream_repo_02["path"] / name).write_text(content, encoding="utf-8")
        upstream.index.add(name)

    upstream.index.commit("Add filter test templates")

    return await InfrahubRepository.new(
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


async def test_worker_rejects_local_only_filter(
    git_repo_filter_tests: InfrahubRepository, init_service: InfrahubServices, prefect_test_fixture: None
) -> None:
    with pytest.raises(TransformError, match="'safe' filter isn't allowed to be used"):
        await transform_render_jinja2_template(message=_make_message(git_repo_filter_tests, "template_safe.tpl.j2"))


async def test_worker_allows_trusted_filters(
    git_repo_filter_tests: InfrahubRepository, init_service: InfrahubServices, prefect_test_fixture: None
) -> None:
    result = await transform_render_jinja2_template(
        message=_make_message(git_repo_filter_tests, "template_upper.tpl.j2")
    )
    assert result == "ONE\nTWO\n"
