from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.protocols import CoreTransformJinja2

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.git import InfrahubRepository
from tests.helpers.file_repo import FileRepo
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase

TASK_RUN_LOGGER = "prefect.task_runs"


class TestClosureFailureIsolation(TestInfrahubApp):
    """A malformed Jinja2 template in one transform must not poison its siblings.

    The repository carries two Jinja2 transforms: one well-formed with a transitive
    include and one whose template has a syntax error. After import, the malformed
    transform is still persisted but flagged ``dependencies_complete = False``, while
    the well-formed transform imports with a complete, populated closure. The
    closure-builder failure is reported in the import log naming the offending
    transform.
    """

    @pytest.fixture(autouse=True)
    def propagate_task_logs(self) -> Generator[None, None, None]:
        logger = logging.getLogger(TASK_RUN_LOGGER)
        original = logger.propagate
        logger.propagate = True
        yield
        logger.propagate = original

    @pytest.fixture(scope="class")
    def git_repo(self, git_sources_dir: Path) -> FileRepo:
        return FileRepo(name="closure-failure-isolation", sources_directory=git_sources_dir)

    @pytest.fixture(scope="class")
    async def repo(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        git_repo: FileRepo,
        git_repos_dir: Path,
    ) -> InfrahubRepository:
        obj = await Node.init(schema=InfrahubKind.REPOSITORY, db=db)
        await obj.new(
            db=db,
            name=git_repo.name,
            description="test repository",
            location="git@github.com:mock/test.git",
        )
        await obj.save(db=db)

        return await InfrahubRepository.new(
            id=obj.id,
            name=git_repo.name,
            location=git_repo.path,
            client=client,
        )

    async def test_malformed_transform_is_isolated_at_import(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        repo: InfrahubRepository,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        commit = repo.get_commit_value(branch_name="main")
        config_file = await repo.get_repository_config(branch_name="main", commit=commit)  # type: ignore[call-overload]
        assert config_file

        # Queries must exist before the Jinja2 transforms that reference them are imported.
        await repo.import_all_graphql_query(branch_name="main", commit=commit, config_file=config_file)  # type: ignore[call-overload]

        with caplog.at_level(logging.INFO, logger=TASK_RUN_LOGGER):
            await repo.import_jinja2_transforms(branch_name="main", commit=commit, config_file=config_file)  # type: ignore[call-overload]

        transforms = {transform.name.value: transform for transform in await client.all(kind=CoreTransformJinja2)}

        # Both transforms are imported: the malformed one is flagged, not dropped.
        assert set(transforms) == {"well_formed_report", "broken_report"}

        well_formed = transforms["well_formed_report"]
        assert well_formed.dependencies_complete.value is True
        assert set(well_formed.dependencies.value) == {
            ".infrahub.yml",
            "templates/partial.j2",
            "templates/report.j2",
        }

        broken = transforms["broken_report"]
        assert broken.dependencies_complete.value is False

        # The closure-builder failure is reported against the offending transform only,
        # naming the unresolved reference and the resulting incomplete closure.
        assert "Closure builder for transform 'broken_report' encountered unresolved reference" in caplog.text
        assert "dependencies_complete=False" in caplog.text
        assert "Closure builder for transform 'well_formed_report'" not in caplog.text
