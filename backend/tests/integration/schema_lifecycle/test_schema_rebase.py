from typing import Any

import pytest
from infrahub_sdk import InfrahubClient

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.diff.repository.repository import DiffRepository
from infrahub.core.initialization import create_branch
from infrahub.core.merge.schema_analyzer import MergeSchemaAnalyzer
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.registry import get_component_registry
from tests.helpers.test_app import TestInfrahubApp

WIDGET_KIND = "TestingWidget"
BRANCH_NAME = "rebase-branch"


def _widget_schema(*attribute_names: str) -> dict[str, Any]:
    return {
        "version": "1.0",
        "nodes": [
            {
                "name": "Widget",
                "namespace": "Testing",
                "generate_profile": False,
                "attributes": [{"name": attr, "kind": "Text", "optional": True} for attr in attribute_names],
            }
        ],
    }


async def _build_schema_analyzer(
    db: InfrahubDatabase, source_branch: Branch, destination_branch: Branch
) -> MergeSchemaAnalyzer:
    component_registry = get_component_registry()
    diff_repository = await component_registry.get_component(DiffRepository, db=db, branch=source_branch)
    return MergeSchemaAnalyzer(
        db=db,
        source_branch=source_branch,
        destination_branch=destination_branch,
        diff_repository=diff_repository,
        schema_manager=registry.schema,
    )


class TestSchemaRebase(TestInfrahubApp):
    """Rebase interactions with the schema, sharing a single rebased-branch setup.

    The branch adds ``size`` and main adds ``color`` after the branch is created; rebasing folds
    main's ``color`` into the branch.
    """

    @pytest.fixture(scope="class")
    async def rebased_branch(self, db: InfrahubDatabase, initialize_registry: None, client: InfrahubClient) -> str:
        response = await client.schema.load(schemas=[_widget_schema("name")])
        assert not response.errors

        await create_branch(db=db, branch_name=BRANCH_NAME)

        # the branch adds its own attribute
        response = await client.schema.load(schemas=[_widget_schema("name", "size")], branch=BRANCH_NAME)
        assert not response.errors

        # main gains a different attribute after the branch was created
        response = await client.schema.load(schemas=[_widget_schema("name", "color")])
        assert not response.errors

        # rebasing folds main's `color` into the branch
        await client.branch.rebase(branch_name=BRANCH_NAME)
        return BRANCH_NAME

    async def test_rebase_merge_baseline(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        client: InfrahubClient,
        rebased_branch: str,
    ) -> None:
        """The 3-way merge diff must be based on the rebase point, not the original branch point.

        Only the branch's real change (``size``) relative to the rebase point should show; ``color``
        was already on main when the branch was rebased and must not resurface as a branch change.
        """
        branch = await Branch.get_by_name(name=rebased_branch, db=db)
        analyzer = await _build_schema_analyzer(db=db, source_branch=branch, destination_branch=default_branch)
        diff_3way = await analyzer.get_3ways_diff_schema()

        assert WIDGET_KIND in diff_3way.changed
        widget_attr_diff = diff_3way.changed[WIDGET_KIND].changed.get("attributes")
        assert widget_attr_diff is not None
        assert set(widget_attr_diff.added.keys()) == {"size"}

    async def test_schema_load_on_rebased_branch(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        rebased_branch: str,
    ) -> None:
        """Loading a schema on the rebased branch must succeed without core kinds surfacing as changed.

        This test was created to troubleshoot a specific issue in SchemaBranch.process() that resulted
        in CoreProfile attributes showing as illegally changed in the schema diff following a rebase.
        """
        response = await client.schema.load(
            schemas=[_widget_schema("name", "size", "color", "weight")], branch=rebased_branch
        )
        assert not response.errors

        # the diff for a further update excludes CoreProfile (only Widget changes)
        branch = await Branch.get_by_name(name=rebased_branch, db=db)
        branch_schema = registry.schema.get_schema_branch(name=branch.name)
        candidate = branch_schema.duplicate()
        candidate.load_schema(schema=SchemaRoot(**_widget_schema("name", "size", "color", "weight", "depth")))
        candidate.process()
        diff = branch_schema.diff(other=candidate)
        assert "CoreProfile" not in diff.changed, diff.changed.get("CoreProfile")
