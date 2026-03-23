from unittest.mock import MagicMock

import pytest

from infrahub.git.integrator import InfrahubRepositoryIntegrator, TransformPythonInformation


class TestTransformPythonInformation:
    def test_description_field_default(self) -> None:
        info = TransformPythonInformation(
            name="test",
            repository="repo-id",
            file_path="transforms/test.py",
            query="query-id",
            class_name="TestTransform",
            transform_class=MagicMock(),
            timeout=10,
            convert_query_response=False,
        )
        assert info.description is None

    def test_description_field_with_value(self) -> None:
        info = TransformPythonInformation(
            name="test",
            repository="repo-id",
            file_path="transforms/test.py",
            query="query-id",
            class_name="TestTransform",
            transform_class=MagicMock(),
            timeout=10,
            convert_query_response=False,
            description="A useful transform",
        )
        assert info.description == "A useful transform"


def _make_mock_transform(
    query_id: str = "query-id",
    file_path: str = "transforms/test.py",
    timeout: int = 10,
    convert_query_response: bool = False,
    description: str | None = None,
) -> MagicMock:
    mock = MagicMock()
    mock.query.id = query_id
    mock.file_path.value = file_path
    mock.timeout.value = timeout
    mock.convert_query_response.value = convert_query_response
    mock.description.value = description
    return mock


def _make_local_transform(**kwargs: object) -> TransformPythonInformation:
    defaults: dict[str, object] = {
        "name": "test",
        "repository": "repo-id",
        "file_path": "transforms/test.py",
        "query": "query-id",
        "class_name": "TestTransform",
        "transform_class": MagicMock(),
        "timeout": 10,
        "convert_query_response": False,
        "description": None,
    }
    defaults.update(kwargs)
    return TransformPythonInformation(**defaults)  # type: ignore[arg-type]


class TestComparePythonTransform:
    @pytest.mark.anyio
    async def test_identical_returns_true(self) -> None:
        existing = _make_mock_transform()
        local = _make_local_transform()
        assert await InfrahubRepositoryIntegrator.compare_python_transform(existing, local) is True

    @pytest.mark.anyio
    async def test_description_changed_returns_false(self) -> None:
        existing = _make_mock_transform(description=None)
        local = _make_local_transform(description="New description")
        assert await InfrahubRepositoryIntegrator.compare_python_transform(existing, local) is False

    @pytest.mark.anyio
    async def test_description_removed_returns_false(self) -> None:
        existing = _make_mock_transform(description="Old description")
        local = _make_local_transform(description=None)
        assert await InfrahubRepositoryIntegrator.compare_python_transform(existing, local) is False

    @pytest.mark.anyio
    async def test_description_same_returns_true(self) -> None:
        existing = _make_mock_transform(description="Same")
        local = _make_local_transform(description="Same")
        assert await InfrahubRepositoryIntegrator.compare_python_transform(existing, local) is True
