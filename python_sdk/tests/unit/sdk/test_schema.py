import inspect

import pytest

from infrahub_sdk import InfrahubClient, InfrahubClientSync, ValidationError
from infrahub_sdk.exceptions import SchemaNotFoundError
from infrahub_sdk.schema import (
    InfrahubCheckDefinitionConfig,
    InfrahubJinja2TransformConfig,
    InfrahubPythonTransformConfig,
    InfrahubRepositoryArtifactDefinitionConfig,
    InfrahubRepositoryConfig,
    InfrahubSchema,
    InfrahubSchemaSync,
    NodeSchema,
)

async_schema_methods = [method for method in dir(InfrahubSchema) if not method.startswith("_")]
sync_schema_methods = [method for method in dir(InfrahubSchemaSync) if not method.startswith("_")]

client_types = ["standard", "sync"]


async def test_method_sanity():
    """Validate that there is at least one public method and that both clients look the same."""
    assert async_schema_methods
    assert async_schema_methods == sync_schema_methods


@pytest.mark.parametrize("method", async_schema_methods)
async def test_validate_method_signature(method):
    async_method = getattr(InfrahubSchema, method)
    sync_method = getattr(InfrahubSchemaSync, method)
    async_sig = inspect.signature(async_method)
    sync_sig = inspect.signature(sync_method)
    assert async_sig.parameters == sync_sig.parameters
    assert async_sig.return_annotation == sync_sig.return_annotation


@pytest.mark.parametrize("client_type", client_types)
async def test_fetch_schema(mock_schema_query_01, client_type):  # pylint: disable=unused-argument
    if client_type == "standard":
        client = await InfrahubClient.init(address="http://mock", insert_tracker=True)
        nodes = await client.schema.fetch(branch="main")
    else:
        client = InfrahubClientSync.init(address="http://mock", insert_tracker=True)
        nodes = client.schema.fetch(branch="main")

    assert len(nodes) == 4
    assert sorted(nodes.keys()) == [
        "BuiltinLocation",
        "BuiltinTag",
        "CoreGraphQLQuery",
        "CoreRepository",
    ]
    assert isinstance(nodes["BuiltinTag"], NodeSchema)


@pytest.mark.parametrize("client_type", client_types)
async def test_schema_data_validation(rfile_schema, client_type):
    if client_type == "standard":
        client = await InfrahubClient.init(address="http://mock", insert_tracker=True)
    else:
        client = InfrahubClientSync.init(address="http://mock", insert_tracker=True)

    client.schema.validate_data_against_schema(
        schema=rfile_schema,
        data={"name": "some-name", "description": "Some description"},
    )

    with pytest.raises(ValidationError) as excinfo:
        client.schema.validate_data_against_schema(
            schema=rfile_schema, data={"name": "some-name", "invalid_field": "yes"}
        )

    assert "invalid_field is not a valid value for CoreTransformJinja2" == excinfo.value.message


@pytest.mark.parametrize("client_type", client_types)
async def test_add_dropdown_option(clients, client_type, mock_schema_query_01, mock_query_mutation_schema_dropdown_add):
    if client_type == "standard":
        await clients.standard.schema.add_dropdown_option("BuiltinTag", "status", "something")
    else:
        clients.sync.schema.add_dropdown_option("BuiltinTag", "status", "something")


@pytest.mark.parametrize("client_type", client_types)
async def test_remove_dropdown_option(
    clients, client_type, mock_schema_query_01, mock_query_mutation_schema_dropdown_remove
):
    if client_type == "standard":
        await clients.standard.schema.remove_dropdown_option("BuiltinTag", "status", "active")
    else:
        clients.sync.schema.remove_dropdown_option("BuiltinTag", "status", "active")


@pytest.mark.parametrize("client_type", client_types)
async def test_add_enum_option(clients, client_type, mock_schema_query_01, mock_query_mutation_schema_enum_add):
    if client_type == "standard":
        await clients.standard.schema.add_enum_option("BuiltinTag", "mode", "hard")
    else:
        clients.sync.schema.add_enum_option("BuiltinTag", "mode", "hard")


@pytest.mark.parametrize("client_type", client_types)
async def test_remove_enum_option(clients, client_type, mock_schema_query_01, mock_query_mutation_schema_enum_remove):
    if client_type == "standard":
        await clients.standard.schema.remove_enum_option("BuiltinTag", "mode", "easy")
    else:
        clients.sync.schema.remove_enum_option("BuiltinTag", "mode", "easy")


@pytest.mark.parametrize("client_type", client_types)
async def test_add_dropdown_option_raises(clients, client_type, mock_schema_query_01):
    if client_type == "standard":
        with pytest.raises(SchemaNotFoundError):
            await clients.standard.schema.add_dropdown_option("DoesNotExist", "atribute", "option")
        with pytest.raises(ValueError):
            await clients.standard.schema.add_dropdown_option("BuiltinTag", "attribute", "option")
    else:
        with pytest.raises(SchemaNotFoundError):
            clients.sync.schema.add_dropdown_option("DoesNotExist", "atribute", "option")
        with pytest.raises(ValueError):
            clients.sync.schema.add_dropdown_option("BuiltinTag", "attribute", "option")


@pytest.mark.parametrize("client_type", client_types)
async def test_add_enum_option_raises(clients, client_type, mock_schema_query_01):
    if client_type == "standard":
        with pytest.raises(SchemaNotFoundError):
            await clients.standard.schema.add_enum_option("DoesNotExist", "atribute", "option")
        with pytest.raises(ValueError):
            await clients.standard.schema.add_enum_option("BuiltinTag", "attribute", "option")
    else:
        with pytest.raises(SchemaNotFoundError):
            clients.sync.schema.add_enum_option("DoesNotExist", "atribute", "option")
        with pytest.raises(ValueError):
            clients.sync.schema.add_enum_option("BuiltinTag", "attribute", "option")


@pytest.mark.parametrize("client_type", client_types)
async def test_remove_dropdown_option_raises(clients, client_type, mock_schema_query_01):
    if client_type == "standard":
        with pytest.raises(SchemaNotFoundError):
            await clients.standard.schema.remove_dropdown_option("DoesNotExist", "atribute", "option")
        with pytest.raises(ValueError):
            await clients.standard.schema.remove_dropdown_option("BuiltinTag", "attribute", "option")
    else:
        with pytest.raises(SchemaNotFoundError):
            clients.sync.schema.remove_dropdown_option("DoesNotExist", "atribute", "option")
        with pytest.raises(ValueError):
            clients.sync.schema.remove_dropdown_option("BuiltinTag", "attribute", "option")


@pytest.mark.parametrize("client_type", client_types)
async def test_remove_enum_option_raises(clients, client_type, mock_schema_query_01):
    if client_type == "standard":
        with pytest.raises(SchemaNotFoundError):
            await clients.standard.schema.remove_enum_option("DoesNotExist", "atribute", "option")
        with pytest.raises(ValueError):
            await clients.standard.schema.remove_enum_option("BuiltinTag", "attribute", "option")
    else:
        with pytest.raises(SchemaNotFoundError):
            clients.sync.schema.add_enum_option("DoesNotExist", "atribute", "option")
        with pytest.raises(ValueError):
            clients.sync.schema.add_enum_option("BuiltinTag", "attribute", "option")


async def test_infrahub_repository_config_getters():
    repo_config = InfrahubRepositoryConfig(
        jinja2_transforms=[
            InfrahubJinja2TransformConfig(name="rfile01", query="query01", template_path="."),
            InfrahubJinja2TransformConfig(name="rfile02", query="query01", template_path="."),
        ],
        artifact_definitions=[
            InfrahubRepositoryArtifactDefinitionConfig(
                name="artifact01",
                parameters={},
                content_type="JSON",
                targets="group1",
                transformation="transformation01",
            ),
            InfrahubRepositoryArtifactDefinitionConfig(
                name="artifact02",
                parameters={},
                content_type="JSON",
                targets="group2",
                transformation="transformation01",
            ),
        ],
        check_definitions=[
            InfrahubCheckDefinitionConfig(name="check01", file_path=".", parameters={}, class_name="MyClass"),
            InfrahubCheckDefinitionConfig(name="check02", file_path=".", parameters={}, class_name="MyClass"),
        ],
        python_transforms=[
            InfrahubPythonTransformConfig(name="transform01", file_path=".", class_name="MyClass"),
            InfrahubPythonTransformConfig(name="transform02", file_path=".", class_name="MyClass"),
        ],
    )

    assert repo_config.has_jinja2_transform(name="rfile01") is True
    assert repo_config.has_jinja2_transform(name="rfile99") is False
    assert isinstance(repo_config.get_jinja2_transform(name="rfile01"), InfrahubJinja2TransformConfig)

    assert repo_config.has_artifact_definition(name="artifact01") is True
    assert repo_config.has_artifact_definition(name="artifact99") is False
    assert isinstance(
        repo_config.get_artifact_definition(name="artifact01"), InfrahubRepositoryArtifactDefinitionConfig
    )

    assert repo_config.has_check_definition(name="check01") is True
    assert repo_config.has_check_definition(name="check99") is False
    assert isinstance(repo_config.get_check_definition(name="check01"), InfrahubCheckDefinitionConfig)

    assert repo_config.has_python_transform(name="transform01") is True
    assert repo_config.has_python_transform(name="transform99") is False
    assert isinstance(repo_config.get_python_transform(name="transform01"), InfrahubPythonTransformConfig)


async def test_infrahub_repository_config_dups():
    with pytest.raises(ValueError) as exc:
        InfrahubRepositoryConfig(
            jinja2_transforms=[
                InfrahubJinja2TransformConfig(name="rfile01", query="query01", template_path="."),
                InfrahubJinja2TransformConfig(name="rfile02", query="query01", template_path="."),
                InfrahubJinja2TransformConfig(name="rfile02", query="query01", template_path="."),
            ],
        )

    assert "Found multiples element with the same names: ['rfile02']" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        InfrahubRepositoryConfig(
            check_definitions=[
                InfrahubCheckDefinitionConfig(name="check01", file_path=".", parameters={}, class_name="MyClass"),
                InfrahubCheckDefinitionConfig(name="check01", file_path=".", parameters={}, class_name="MyClass"),
                InfrahubCheckDefinitionConfig(name="check02", file_path=".", parameters={}, class_name="MyClass"),
                InfrahubCheckDefinitionConfig(name="check02", file_path=".", parameters={}, class_name="MyClass"),
                InfrahubCheckDefinitionConfig(name="check02", file_path=".", parameters={}, class_name="MyClass"),
                InfrahubCheckDefinitionConfig(name="check03", file_path=".", parameters={}, class_name="MyClass"),
            ],
        )

    assert "Found multiples element with the same names: ['check01', 'check02']" in str(exc.value)
