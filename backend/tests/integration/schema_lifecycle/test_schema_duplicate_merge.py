"""Test that merging a branch fails when the same schema is loaded on both branches."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from infrahub_sdk.exceptions import GraphQLError

from infrahub.core import registry
from infrahub.core.initialization import create_branch
from tests.constants import TestKind
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase


class TestSchemaDuplicateMerge(TestInfrahubApp):
    """Test that loading the same schema on both main and branch causes merge to fail.

    This test verifies the expected behavior when:
    1. The base schema (internal + core) is initialized
    2. A branch is created
    3. A user schema (CAR_SCHEMA) is loaded on the default branch
    4. The same user schema is loaded on the created branch
    5. An attempt to merge the branch should fail due to duplicate schema elements
    """

    async def test_merge_branch_with_duplicate_schema(
        self,
        db: InfrahubDatabase,
        client: InfrahubClient,
        default_branch: Branch,
        initialize_registry: None,
    ) -> None:
        """Attempt to merge the branch - should fail due to duplicate schema elements."""
        # Create the branch
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        await registry.schema.update_schema_branch(
            db=db, schema=schema_branch.duplicate(), branch=default_branch.name, update_db=True
        )

        branch = await create_branch(db=db, branch_name="schema_duplicate_branch")

        # Load CAR_SCHEMA on the default branch
        await load_schema(
            db=db,
            schema=CAR_SCHEMA.duplicate(),
            branch_name=default_branch.name,
            limit=[TestKind.CAR, TestKind.MANUFACTURER, TestKind.PERSON],
            update_db=True,
        )

        # Load the same CAR_SCHEMA on the branch
        await load_schema(
            db=db,
            schema=CAR_SCHEMA.duplicate(),
            branch_name=branch.name,
            limit=[TestKind.CAR, TestKind.MANUFACTURER, TestKind.PERSON],
            update_db=True,
        )

        # Attempt to merge - should fail due to duplicate schema elements
        with pytest.raises(GraphQLError) as excinfo:
            await client.branch.merge(branch_name=branch.name)

        # Verify the error mentions uniqueness constraint violation on SchemaNode
        error_message = str(excinfo.value)

        duplicate_schema_uuids = []
        for schema_kind in [TestKind.CAR, TestKind.MANUFACTURER, TestKind.PERSON]:
            for branch_name in [default_branch.name, branch.name]:
                schema = registry.schema.get_node_schema(name=schema_kind, branch=branch_name, duplicate=False)
                duplicate_schema_uuids.append(schema.get_id())

        assert "constraint violation on schema 'SchemaNode'" in error_message
        assert all(uuid in error_message for uuid in duplicate_schema_uuids)
