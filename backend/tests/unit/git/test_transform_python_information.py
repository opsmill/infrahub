from unittest.mock import MagicMock

from infrahub_sdk import Config, InfrahubClient
from infrahub_sdk.node import InfrahubNode
from infrahub_sdk.protocols import CoreTransformPython
from infrahub_sdk.schema import AttributeSchemaAPI, NodeSchemaAPI, RelationshipSchemaAPI
from infrahub_sdk.schema.main import AttributeKind, RelationshipCardinality, RelationshipKind

from infrahub.git.integrator import InfrahubRepositoryIntegrator, TransformPythonInformation

TRANSFORM_PYTHON_SCHEMA = NodeSchemaAPI(
    name="TransformPython",
    namespace="Core",
    attributes=[
        AttributeSchemaAPI(name="name", kind=AttributeKind.TEXT),
        AttributeSchemaAPI(name="label", kind=AttributeKind.TEXT, optional=True),
        AttributeSchemaAPI(name="description", kind=AttributeKind.TEXT, optional=True),
        AttributeSchemaAPI(name="file_path", kind=AttributeKind.TEXT),
        AttributeSchemaAPI(name="class_name", kind=AttributeKind.TEXT),
        AttributeSchemaAPI(name="timeout", kind=AttributeKind.NUMBER),
        AttributeSchemaAPI(name="convert_query_response", kind=AttributeKind.BOOLEAN, optional=True),
    ],
    relationships=[
        RelationshipSchemaAPI(
            name="query",
            peer="CoreGraphQLQuery",
            kind=RelationshipKind.ATTRIBUTE,
            cardinality=RelationshipCardinality.ONE,
        ),
        RelationshipSchemaAPI(
            name="repository",
            peer="CoreRepository",
            kind=RelationshipKind.ATTRIBUTE,
            cardinality=RelationshipCardinality.ONE,
        ),
    ],
)


def _make_existing_transform(
    query_id: str = "query-id",
    file_path: str = "transforms/test.py",
    timeout: int = 10,
    convert_query_response: bool = False,
    description: str | None = None,
) -> CoreTransformPython:
    client = InfrahubClient(config=Config(address="http://mock"))
    data = {
        "id": "a0d4c22a-5f60-4bf9-a53f-f9a335420492",
        "__typename": "CoreTransformPython",
        "display_label": "test-transform",
        "name": {"value": "test", "__typename": "Text"},
        "label": {"value": "Test", "__typename": "Text"},
        "description": {"value": description, "__typename": "Text"},
        "file_path": {"value": file_path, "__typename": "Text"},
        "class_name": {"value": "TestTransform", "__typename": "Text"},
        "timeout": {"value": timeout, "__typename": "Number"},
        "convert_query_response": {"value": convert_query_response, "__typename": "Boolean"},
        "query": {
            "node": {"id": query_id, "display_label": "test-query", "__typename": "CoreGraphQLQuery"},
            "__typename": "NestedEdgedCoreGraphQLQuery",
        },
        "repository": {
            "node": {"id": "repo-id", "display_label": "test-repo", "__typename": "CoreRepository"},
            "__typename": "NestedEdgedCoreRepository",
        },
    }
    return InfrahubNode(client=client, schema=TRANSFORM_PYTHON_SCHEMA, data=data)  # type: ignore[return-value]


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


class TestComparePythonTransform:
    async def test_identical_returns_true(self) -> None:
        existing = _make_existing_transform()
        local = _make_local_transform()
        assert await InfrahubRepositoryIntegrator.compare_python_transform(existing, local) is True

    async def test_description_changed_returns_false(self) -> None:
        existing = _make_existing_transform(description=None)
        local = _make_local_transform(description="New description")
        assert await InfrahubRepositoryIntegrator.compare_python_transform(existing, local) is False

    async def test_description_removed_returns_false(self) -> None:
        existing = _make_existing_transform(description="Old description")
        local = _make_local_transform(description=None)
        assert await InfrahubRepositoryIntegrator.compare_python_transform(existing, local) is False

    async def test_description_same_returns_true(self) -> None:
        existing = _make_existing_transform(description="Same")
        local = _make_local_transform(description="Same")
        assert await InfrahubRepositoryIntegrator.compare_python_transform(existing, local) is True
