from unittest.mock import AsyncMock, patch

import pytest

from infrahub.core.branch import Branch
from infrahub.core.diff.models import RequestDiffUpdate
from infrahub.core.diff.tasks import update_diff
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.component.registry import ComponentDependencyRegistry
from infrahub.dependencies.registry import get_component_registry


class DummyComponentRegistry:
    async def get_component(self, *args, **kwargs):
        mock_component = AsyncMock()
        # Needed so .run_update can be awaited and does nothing
        mock_component.run_update = AsyncMock()
        return mock_component


@pytest.fixture
def wrapped_component_registry() -> ComponentDependencyRegistry:
    component_registry = get_component_registry()
    wrapped_component_registry = AsyncMock(wraps=component_registry)

    with patch("infrahub.dependencies.registry.get_component_registry", return_value=wrapped_component_registry):
        yield wrapped_component_registry


async def test_diff_update_for_deleted_branch(
    db: InfrahubDatabase, default_branch: Branch, wrapped_component_registry: ComponentDependencyRegistry
) -> None:
    diff_update = RequestDiffUpdate(branch_name="pretend_branch", name="diff")

    await update_diff(diff_update)

    wrapped_component_registry.get_component.assert_not_awaited()
