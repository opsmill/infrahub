import pytest
from infrahub_sdk import InfrahubClient
from infrahub_sdk.uuidt import UUIDT

from infrahub.core.constants import InfrahubKind
from infrahub.exceptions import RepositoryFileNotFoundError, TransformError
from infrahub.git import InfrahubRepository
from infrahub.services import InfrahubServices, services
from infrahub.transformations.models import TransformJinjaTemplateData, TransformPythonData
from infrahub.transformations.tasks import transform_python, transform_render_jinja2_template


@pytest.fixture
def init_service():
    original = services.service
    service = InfrahubServices(client=InfrahubClient())
    services.service = service
    yield service
    services.service = original


async def test_git_transform_jinja2_success(git_repo_jinja: InfrahubRepository, prefect_test_fixture, helper):
    commit = git_repo_jinja.get_commit_value(branch_name="main")
    message = TransformJinjaTemplateData(
        repository_id=str(UUIDT()),
        repository_name=git_repo_jinja.name,
        repository_kind=InfrahubKind.REPOSITORY,
        commit=commit,
        branch="main",
        template_location="template01.tpl.j2",
        data={"items": ["consilium", "potum", "album", "magnum"]},
    )
    expected_response = """
consilium
potum
album
magnum
"""
    response = await transform_render_jinja2_template(message=message)
    assert response == expected_response


async def test_git_transform_jinja2_missing(git_repo_jinja: InfrahubRepository, prefect_test_fixture, helper):
    commit = git_repo_jinja.get_commit_value(branch_name="main")

    message = TransformJinjaTemplateData(
        repository_id=str(UUIDT()),
        repository_name=git_repo_jinja.name,
        repository_kind=InfrahubKind.REPOSITORY,
        commit=commit,
        branch="main",
        template_location="template03.tpl.j2",
        data={"data": {"items": ["consilium", "potum", "album", "magnum"]}},
    )

    with pytest.raises(RepositoryFileNotFoundError) as exc:
        await transform_render_jinja2_template(message=message)

    assert "Unable to find the file" in exc.value.message


async def test_git_transform_jinja2_invalid(git_repo_jinja: InfrahubRepository, prefect_test_fixture, helper, caplog):
    commit = git_repo_jinja.get_commit_value(branch_name="main")

    message = TransformJinjaTemplateData(
        repository_id=str(UUIDT()),
        repository_name=git_repo_jinja.name,
        repository_kind=InfrahubKind.REPOSITORY,
        commit=commit,
        branch="main",
        template_location="template02.tpl.j2",
        data={"data": {"items": ["consilium", "potum", "album", "magnum"]}},
    )

    with pytest.raises(TransformError) as exc:
        await transform_render_jinja2_template(message=message)

    assert "Encountered unknown tag" in exc.value.message


async def test_transform_python_success(
    git_fixture_repo: InfrahubRepository, init_service, prefect_test_fixture, helper
):
    commit = git_fixture_repo.get_commit_value(branch_name="main")

    message = TransformPythonData(
        repository_id=str(git_fixture_repo.id),
        repository_name=git_fixture_repo.name,
        repository_kind=InfrahubKind.REPOSITORY,
        commit=commit,
        branch="main",
        transform_location="unit/transforms/multiplier.py::Multiplier",
        data={"multiplier": 2, "key": "abc", "answer": 21},
    )

    response = await transform_python(message=message)
    assert response == {"key": "abcabc", "answer": 42}
