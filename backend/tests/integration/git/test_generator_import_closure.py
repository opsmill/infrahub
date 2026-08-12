from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.protocols import CoreGeneratorDefinition

from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.git import InfrahubRepository
from infrahub.git.repository import get_initialized_repo
from tests.constants import TestKind
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.database import InfrahubDatabase

# Every generator in the fixture lives in the `generators/` package, so each one's
# closure is the package-directory floor (every tracked file under that directory)
# plus the repository config file, which the aggregator includes for every definition.
GENERATOR_PACKAGE_CLOSURE = {
    ".infrahub.yml",
    "generators/__init__.py",
    "generators/cartags.gql",
    "generators/cartags.py",
    "generators/cartags_convert_response.py",
    "generators/cartags_title.py",
    "generators/cartags_upper.py",
}

GENERATOR_NAMES = {"cartags", "cartags_convert_response", "cartags_title", "cartags_upper"}


class TestGeneratorImportClosure(TestInfrahubApp):
    """Importing a repository builds and persists a dependency closure on every generator definition.

    Each generator's closure is the package-directory floor of its source file. A
    re-import after the stored closure has drifted from the worktree must rewrite it:
    the closure comparison is the one behavior this carries that the legacy import
    gate did not, so a content change altering only the closure still triggers an
    update.
    """

    @pytest.fixture(scope="class")
    async def initial_dataset(
        self,
        db: InfrahubDatabase,
        initialize_registry: None,
        git_repos_dir_module_scope: Path,
        git_repos_source_dir_module_scope: Path,
    ) -> None:
        await load_schema(db, schema=CAR_SCHEMA)
        FileRepo(name="car-dealership", sources_directory=git_repos_source_dir_module_scope)
        john = await Node.init(schema=TestKind.PERSON, db=db)
        await john.new(db=db, name="John", height=175, age=25)
        await john.save(db=db)
        people = await Node.init(schema=InfrahubKind.STANDARDGROUP, db=db)
        await people.new(db=db, name="people", members=[john])
        await people.save(db=db)

    @pytest.fixture(scope="class")
    async def repository_id(
        self,
        initial_dataset: None,
        git_repos_source_dir_module_scope: Path,
        client: InfrahubClient,
    ) -> str:
        client_repository = await client.create(
            kind=InfrahubKind.REPOSITORY,
            data={"name": "car-dealership", "location": f"{git_repos_source_dir_module_scope}/car-dealership"},
        )
        await client_repository.save()
        return client_repository.id

    async def test_import_persists_closure_on_each_generator(
        self,
        repository_id: str,
        client: InfrahubClient,
    ) -> None:
        generators = {gen.name.value: gen for gen in await client.all(kind=CoreGeneratorDefinition)}

        assert set(generators) == GENERATOR_NAMES
        for generator in generators.values():
            assert set(generator.dependencies.value) == GENERATOR_PACKAGE_CLOSURE
            assert generator.dependencies_complete.value is True

    async def test_reimport_rewrites_drifted_closure(
        self,
        repository_id: str,
        client: InfrahubClient,
    ) -> None:
        repo = await get_initialized_repo(
            client=client,
            repository_id=repository_id,
            name="car-dealership",
            repository_kind=InfrahubKind.REPOSITORY,
        )
        assert isinstance(repo, InfrahubRepository)

        commit = repo.get_commit_value(branch_name="main")
        config_file = await repo.get_repository_config(branch_name="main", commit=commit)  # type: ignore[call-overload]
        assert config_file

        # Drift the stored closure away from the worktree while leaving every other
        # compared field intact, so only the closure comparison can trigger the update.
        stale = (await client.filters(kind=CoreGeneratorDefinition, name__value="cartags"))[0]
        stale.dependencies.value = ["generators/cartags.py"]
        stale.dependencies_complete.value = False
        await stale.save()

        await repo.import_generator_definitions(branch_name="main", commit=commit, config_file=config_file)  # type: ignore[call-overload]

        refreshed = (await client.filters(kind=CoreGeneratorDefinition, name__value="cartags"))[0]
        assert set(refreshed.dependencies.value) == GENERATOR_PACKAGE_CLOSURE
        assert refreshed.dependencies_complete.value is True
