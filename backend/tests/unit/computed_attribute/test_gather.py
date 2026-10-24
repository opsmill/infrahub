from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from infrahub.computed_attribute import gather
from infrahub.computed_attribute.gather import gather_python_transform_attributes
from infrahub.computed_attribute.models import PythonTransformComputedAttribute
from infrahub.git.models import RepositoryData


async def test_gather_python_transform_attributes_skips_branch_without_repository_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A branch deleted while the gather runs has no repository commit and is skipped instead of raising."""
    schema_branch = MagicMock()
    schema_branch.computed_attributes.python_attributes_by_transform = {"transform01": [MagicMock()]}
    registry = MagicMock()
    registry.schema.get_schema_branch.return_value = schema_branch
    registry.get_altered_schema_branches.return_value = []
    monkeypatch.setattr(gather, "registry", registry)

    repository = MagicMock()
    repository.name.value = "repo01"
    repository.get_id.return_value = "repo-id"
    repository.get_kind.return_value = "CoreRepository"
    query = MagicMock()
    query.query.value = "query { x }"
    query.name.value = "query01"
    transform = MagicMock()
    transform.name.value = "transform01"
    transform.repository.get_peer = AsyncMock(return_value=repository)
    transform.query.get_peer = AsyncMock(return_value=query)

    monkeypatch.setattr(gather.NodeManager, "query", AsyncMock(return_value=[transform]))
    monkeypatch.setattr(gather, "prepare_graphql_params", AsyncMock(return_value=SimpleNamespace(schema=None)))
    monkeypatch.setattr(gather, "cached_parse", MagicMock())
    monkeypatch.setattr(gather, "InfrahubGraphQLQueryAnalyzer", MagicMock())
    monkeypatch.setattr(gather, "PythonTransformComputedAttribute", PythonTransformComputedAttribute.model_construct)
    monkeypatch.setattr(gather, "get_run_logger", MagicMock())

    repositories: dict[str, Any] = {
        "repo01": RepositoryData.model_construct(
            repository_id="repo-id", repository_name="repo01", branches={"main": "abc"}
        )
    }

    deleted = await gather_python_transform_attributes.fn(
        db=MagicMock(), branch_name="deleted-branch", repositories=repositories
    )
    assert deleted == []

    existing = await gather_python_transform_attributes.fn(
        db=MagicMock(), branch_name="main", repositories=repositories
    )
    assert [item.repository_commit for item in existing] == ["abc"]
