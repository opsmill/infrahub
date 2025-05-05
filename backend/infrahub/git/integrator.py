from __future__ import annotations

import hashlib
import importlib
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import ujson
import yaml
from infrahub_sdk import InfrahubClient  # noqa: TC002
from infrahub_sdk.exceptions import ValidationError
from infrahub_sdk.node import InfrahubNode
from infrahub_sdk.protocols import (
    CoreArtifact,
    CoreArtifactDefinition,
    CoreCheckDefinition,
    CoreGeneratorDefinition,
    CoreGenericRepository,
    CoreGraphQLQuery,
    CoreTransformation,
    CoreTransformJinja2,
    CoreTransformPython,
)
from infrahub_sdk.schema.repository import (
    InfrahubCheckDefinitionConfig,
    InfrahubGeneratorDefinitionConfig,
    InfrahubJinja2TransformConfig,
    InfrahubPythonTransformConfig,
    InfrahubRepositoryConfig,
)
from infrahub_sdk.template import Jinja2Template
from infrahub_sdk.template.exceptions import JinjaTemplateError
from infrahub_sdk.utils import compare_lists
from infrahub_sdk.yaml import SchemaFile
from prefect import flow, task
from prefect.cache_policies import NONE
from prefect.logging import get_run_logger
from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError
from typing_extensions import Self

from infrahub.core.constants import ArtifactStatus, ContentType, InfrahubKind, RepositorySyncStatus
from infrahub.core.registry import registry
from infrahub.events.artifact_action import ArtifactCreatedEvent, ArtifactUpdatedEvent
from infrahub.events.models import EventMeta
from infrahub.events.repository_action import CommitUpdatedEvent
from infrahub.exceptions import CheckError, RepositoryInvalidFileSystemError, TransformError
from infrahub.git.base import InfrahubRepositoryBase, extract_repo_file_information
from infrahub.log import get_logger
from infrahub.workflows.utils import add_tags

if TYPE_CHECKING:
    import types

    from infrahub_sdk.checks import InfrahubCheck
    from infrahub_sdk.schema.repository import InfrahubRepositoryArtifactDefinitionConfig
    from infrahub_sdk.transforms import InfrahubTransform

    from infrahub.artifacts.models import CheckArtifactCreate
    from infrahub.git.models import RequestArtifactGenerate
    from infrahub.services import InfrahubServices


class ArtifactGenerateResult(BaseModel):
    changed: bool
    checksum: str
    storage_id: str
    artifact_id: str


class InfrahubRepositoryJinja2(InfrahubJinja2TransformConfig):
    repository: str


class CheckDefinitionInformation(BaseModel):
    name: str
    """Name of the check"""

    repository: str = "self"
    """ID of the associated repository or self"""

    query: str
    """ID or name of the GraphQL Query associated with this Check"""

    file_path: str
    """Path to the python file within the repo"""

    class_name: str
    """Name of the Python Class"""

    check_class: Any
    """Python Class of the Check"""

    timeout: int
    """Timeout for the Check."""

    parameters: dict | None = None
    """Additional Parameters to extract from each target (if targets is provided)"""

    targets: str | None = Field(default=None, description="Targets if not a global check")


class TransformPythonInformation(BaseModel):
    name: str
    """Name of the Transform"""

    repository: str
    """ID or name of the repository this Transform is assocated with"""

    file_path: str
    """file_path of the TransformFunction within the repository"""

    query: str
    """ID or name of the GraphQLQuery this Transform is assocated with"""

    class_name: str
    """Name of the Python Class of the Transform Function"""

    transform_class: Any
    """Python Class of the Transform"""

    timeout: int
    """Timeout for the function."""

    convert_query_response: bool = Field(
        ..., description="Indicate if the transform should convert the query response to InfrahubNode objects"
    )


class InfrahubRepositoryIntegrator(InfrahubRepositoryBase):
    """
    This class provides interfaces to read and process information from .infrahub.yml files and can perform
    actions for objects defined within those files.

    This class will later be broken out from the "InfrahubRepository" based classes and instead be a separate
    class that uses an "InfrahubRepository" or "InfrahubReadOnlyRepository" as input
    """

    @classmethod
    async def init(cls, service: InfrahubServices, commit: str | None = None, **kwargs: Any) -> Self:
        self = cls(service=service, **kwargs)
        log = get_logger()
        try:
            self.validate_local_directories()
        except RepositoryInvalidFileSystemError:
            await self.ensure_location_is_defined()
            await self.create_locally(infrahub_branch_name=self.infrahub_branch_name, update_commit_value=False)
            log.info(f"Initialized the local directory for {self.name} because it was missing.")

        if commit:
            self.get_commit_worktree(commit=commit)

        log.debug(
            f"Initiated the object on an existing directory for {self.name}",
        )
        return self

    async def ensure_location_is_defined(self) -> None:
        if self.location:
            return
        client = self.get_client()
        repo = await client.get(
            kind=CoreGenericRepository, name__value=self.name, exclude=["tags", "credential"], raise_when_missing=True
        )
        self.location = repo.location.value

    @flow(name="import-object-from-file", flow_run_name="Import objects")
    async def import_objects_from_files(
        self, infrahub_branch_name: str, git_branch_name: str | None = None, commit: str | None = None
    ) -> None:
        if not commit:
            commit = self.get_commit_value(branch_name=git_branch_name or infrahub_branch_name)

        await add_tags(branches=[infrahub_branch_name], nodes=[str(self.id)])

        self.create_commit_worktree(commit)
        await self._update_sync_status(branch_name=infrahub_branch_name, status=RepositorySyncStatus.SYNCING)

        config_file = await self.get_repository_config(branch_name=infrahub_branch_name, commit=commit)  # type: ignore[misc]
        sync_status = RepositorySyncStatus.IN_SYNC if config_file else RepositorySyncStatus.ERROR_IMPORT
        error: Exception | None = None

        try:
            if config_file:
                await self.import_schema_files(branch_name=infrahub_branch_name, commit=commit, config_file=config_file)  # type: ignore[misc]

                await self.import_all_graphql_query(
                    branch_name=infrahub_branch_name, commit=commit, config_file=config_file
                )  # type: ignore[misc]

                await self.import_all_python_files(  # type: ignore[call-overload]
                    branch_name=infrahub_branch_name, commit=commit, config_file=config_file
                )  # type: ignore[misc]
                await self.import_jinja2_transforms(
                    branch_name=infrahub_branch_name, commit=commit, config_file=config_file
                )  # type: ignore[misc]
                await self.import_artifact_definitions(
                    branch_name=infrahub_branch_name, commit=commit, config_file=config_file
                )  # type: ignore[misc]

        except Exception as exc:
            sync_status = RepositorySyncStatus.ERROR_IMPORT
            error = exc

        await self._update_sync_status(branch_name=infrahub_branch_name, status=sync_status)

        if error:
            raise error

        infrahub_branch = registry.get_branch_from_registry(branch=infrahub_branch_name)
        await self.service.event.send(
            CommitUpdatedEvent(
                commit=commit,
                repository_name=self.name,
                repository_id=str(self.id),
                meta=EventMeta.with_dummy_context(branch=infrahub_branch),
            )
        )

    @task(name="import-jinja2-tansforms", task_run_name="Import Jinja2 transform", cache_policy=NONE)  # type: ignore[arg-type]
    async def import_jinja2_transforms(
        self,
        branch_name: str,
        commit: str,  # noqa: ARG002
        config_file: InfrahubRepositoryConfig,
    ) -> None:
        log = get_run_logger()

        schema = await self.sdk.schema.get(kind=InfrahubKind.TRANSFORMJINJA2, branch=branch_name)

        transforms_in_graph = {
            transform.name.value: transform
            for transform in await self.sdk.filters(
                kind=CoreTransformJinja2, branch=branch_name, repository__ids=[str(self.id)]
            )
        }

        local_transforms: dict[str, InfrahubRepositoryJinja2] = {}

        # Process the list of local Jinja2 Transforms to organize them by name
        log.info(f"Found {len(config_file.jinja2_transforms)} Jinja2 transforms in the repository")

        for config_transform in config_file.jinja2_transforms:
            try:
                self.sdk.schema.validate_data_against_schema(
                    schema=schema, data=config_transform.model_dump(exclude_none=True)
                )
            except PydanticValidationError as exc:
                for error in exc.errors():
                    locations = [str(error_location) for error_location in error["loc"]]
                    log.error(f"  {'/'.join(locations)} | {error['msg']} ({error['type']})")
                continue
            except ValidationError as exc:
                log.error(exc.message)
                continue

            transform = InfrahubRepositoryJinja2(repository=str(self.id), **config_transform.model_dump())

            # Query the GraphQL query and (eventually) replace the name with the ID
            graphql_query = await self.sdk.get(
                kind=InfrahubKind.GRAPHQLQUERY, branch=branch_name, id=str(transform.query), populate_store=True
            )
            transform.query = graphql_query.id

            local_transforms[transform.name] = transform

        present_in_both, only_graph, only_local = compare_lists(
            list1=list(transforms_in_graph.keys()), list2=list(local_transforms.keys())
        )

        for transform_name in only_local:
            log.info(f"New Jinja2 Transform {transform_name!r} found, creating")
            await self.create_jinja2_transform(branch_name=branch_name, data=local_transforms[transform_name])

        for transform_name in present_in_both:
            if not await self.compare_jinja2_transform(
                existing_transform=transforms_in_graph[transform_name], local_transform=local_transforms[transform_name]
            ):
                log.info(f"New version of the Jinja2 Transform '{transform_name}' found, updating")
                await self.update_jinja2_transform(
                    existing_transform=transforms_in_graph[transform_name],
                    local_transform=local_transforms[transform_name],
                )

        for transform_name in only_graph:
            log.info(f"Jinja2 Transform '{transform_name}' not found locally in branch {branch_name}, deleting")
            await transforms_in_graph[transform_name].delete()

    async def create_jinja2_transform(self, branch_name: str, data: InfrahubRepositoryJinja2) -> CoreTransformJinja2:
        schema = await self.sdk.schema.get(kind=InfrahubKind.TRANSFORMJINJA2, branch=branch_name)
        create_payload = self.sdk.schema.generate_payload_create(
            schema=schema, data=data.payload, source=self.id, is_protected=True
        )
        obj = await self.sdk.create(kind=CoreTransformJinja2, branch=branch_name, **create_payload)
        await obj.save()
        return obj

    @classmethod
    async def compare_jinja2_transform(
        cls, existing_transform: CoreTransformJinja2, local_transform: InfrahubRepositoryJinja2
    ) -> bool:
        if (
            existing_transform.description.value != local_transform.description
            or existing_transform.template_path.value != local_transform.template_path
            or existing_transform.query.id != local_transform.query
        ):
            return False

        return True

    async def update_jinja2_transform(
        self, existing_transform: CoreTransformJinja2, local_transform: InfrahubRepositoryJinja2
    ) -> None:
        if existing_transform.description.value != local_transform.description:
            existing_transform.description.value = local_transform.description

        if existing_transform.query.id != local_transform.query:
            existing_transform.query = {"id": local_transform.query, "source": str(self.id), "is_protected": True}

        if existing_transform.template_path.value != local_transform.template_path_value:
            existing_transform.template_path.value = local_transform.template_path_value

        await existing_transform.save()

    @task(name="import-artifact-definitions", task_run_name="Import Artifact Definitions", cache_policy=NONE)  # type: ignore[arg-type]
    async def import_artifact_definitions(
        self,
        branch_name: str,
        commit: str,  # noqa: ARG002
        config_file: InfrahubRepositoryConfig,
    ) -> None:
        log = get_run_logger()
        schema = await self.sdk.schema.get(kind=InfrahubKind.ARTIFACTDEFINITION, branch=branch_name)

        artifact_defs_in_graph = {
            artdef.name.value: artdef
            for artdef in await self.sdk.filters(
                kind=CoreArtifactDefinition, branch=branch_name, prefetch_relationships=True, populate_store=True
            )
        }

        local_artifact_defs: dict[str, InfrahubRepositoryArtifactDefinitionConfig] = {}

        # Process the list of local Artifact Definitions to organize them by name
        log.info(f"Found {len(config_file.artifact_definitions)} artifact definitions in the repository")

        for artdef in config_file.artifact_definitions:
            try:
                self.sdk.schema.validate_data_against_schema(schema=schema, data=artdef.model_dump(exclude_none=True))
            except PydanticValidationError as exc:
                for error in exc.errors():
                    locations = [str(error_location) for error_location in error["loc"]]
                    log.error(f"  {'/'.join(locations)} | {error['msg']} ({error['type']})")
                continue
            except ValidationError as exc:
                log.error(exc.message)
                continue

            local_artifact_defs[artdef.name] = artdef

        present_in_both, _, only_local = compare_lists(
            list1=list(artifact_defs_in_graph.keys()), list2=list(local_artifact_defs.keys())
        )

        for artdef_name in only_local:
            log.info(f"New Artifact Definition {artdef_name!r} found, creating")
            await self.create_artifact_definition(branch_name=branch_name, data=local_artifact_defs[artdef_name])

        for artdef_name in present_in_both:
            if not await self.compare_artifact_definition(
                existing_artifact_definition=artifact_defs_in_graph[artdef_name],
                local_artifact_definition=local_artifact_defs[artdef_name],
            ):
                log.info(f"New version of the Artifact Definition '{artdef_name}' found, updating")
                await self.update_artifact_definition(
                    existing_artifact_definition=artifact_defs_in_graph[artdef_name],
                    local_artifact_definition=local_artifact_defs[artdef_name],
                )

    async def create_artifact_definition(
        self, branch_name: str, data: InfrahubRepositoryArtifactDefinitionConfig
    ) -> InfrahubNode:
        schema = await self.sdk.schema.get(kind=InfrahubKind.ARTIFACTDEFINITION, branch=branch_name)
        create_payload = self.sdk.schema.generate_payload_create(
            schema=schema, data=data.model_dump(), source=self.id, is_protected=True
        )
        obj = await self.sdk.create(kind=InfrahubKind.ARTIFACTDEFINITION, branch=branch_name, **create_payload)
        await obj.save()
        return obj

    @classmethod
    async def compare_artifact_definition(
        cls,
        existing_artifact_definition: CoreArtifactDefinition,
        local_artifact_definition: InfrahubRepositoryArtifactDefinitionConfig,
    ) -> bool:
        if (
            existing_artifact_definition.artifact_name.value != local_artifact_definition.artifact_name
            or existing_artifact_definition.parameters.value != local_artifact_definition.parameters
            or existing_artifact_definition.content_type.value != local_artifact_definition.content_type
            or existing_artifact_definition.targets.peer.name.value != local_artifact_definition.targets
        ):
            return False

        return True

    async def update_artifact_definition(
        self,
        existing_artifact_definition: CoreArtifactDefinition,
        local_artifact_definition: InfrahubRepositoryArtifactDefinitionConfig,
    ) -> None:
        if existing_artifact_definition.artifact_name.value != local_artifact_definition.artifact_name:
            existing_artifact_definition.artifact_name.value = local_artifact_definition.artifact_name

        if existing_artifact_definition.parameters.value != local_artifact_definition.parameters:
            existing_artifact_definition.parameters.value = local_artifact_definition.parameters

        if existing_artifact_definition.content_type.value != local_artifact_definition.content_type:
            existing_artifact_definition.content_type.value = local_artifact_definition.content_type

        if existing_artifact_definition.targets.peer.name.value != local_artifact_definition.targets:
            existing_artifact_definition.targets = local_artifact_definition.targets

        await existing_artifact_definition.save()

    @task(name="repository-get-config", task_run_name="get repository config", cache_policy=NONE)  # type: ignore[arg-type]
    async def get_repository_config(self, branch_name: str, commit: str) -> InfrahubRepositoryConfig | None:
        branch_wt = self.get_worktree(identifier=commit or branch_name)
        log = get_run_logger()

        config_file_name = ".infrahub.yml"
        config_file = branch_wt.directory / config_file_name
        if not config_file.is_file():
            log.debug(f"Unable to find the configuration file {config_file_name}, skipping")
            return None

        config_file_content = config_file.read_text(encoding="utf-8")
        try:
            data = yaml.safe_load(config_file_content)
        except yaml.YAMLError as exc:
            log.error(f"Unable to load the configuration file in YAML format {config_file_name} : {exc}")
            return None

        # Convert data to a dictionary to avoid it being `None` if the yaml file is just an empty document
        data = data or {}

        try:
            configuration = InfrahubRepositoryConfig(**data)
            log.info(f"Successfully parsed {config_file_name}")
            return configuration
        except PydanticValidationError as exc:
            log.error(f"Unable to load the configuration file {config_file_name}, the format is not valid  : {exc}")
            return None

    @task(name="import-schema-files", task_run_name="Import schema files", cache_policy=NONE)  # type: ignore[arg-type]
    async def import_schema_files(self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig) -> None:
        log = get_run_logger()
        branch_wt = self.get_worktree(identifier=commit or branch_name)

        schemas_data: list[SchemaFile] = []

        for schema in config_file.schemas:
            full_schema = branch_wt.directory / schema
            if not full_schema.exists():
                log.warning(f"Unable to find the schema {schema}")

            if full_schema.is_file():
                schema_file = SchemaFile(identifier=str(schema), location=full_schema)
                schema_file.load_content()
                schemas_data.append(schema_file)
            elif full_schema.is_dir():
                files = await self.find_files(
                    extension=["yaml", "yml", "json"], branch_name=branch_name, commit=commit, directory=full_schema
                )
                for item in files:
                    identifier = str(item.relative_to(branch_wt.directory))
                    schema_file = SchemaFile(identifier=identifier, location=item)
                    schema_file.load_content()
                    schemas_data.append(schema_file)

        if not schemas_data:
            # If the repository doesn't contain any schema files there is no reason to continue
            # and send an empty list to the API
            return

        for schema_file in schemas_data:
            if schema_file.valid:
                continue
            log.error(f"Unable to load the file {schema_file.identifier}, {schema_file.error_message}")

        # Valid data format of content
        for schema_file in schemas_data:
            try:
                self.sdk.schema.validate(schema_file.content)
            except PydanticValidationError as exc:
                log.error(f"Schema not valid, found '{len(exc.errors())}' error(s) in {schema_file.identifier} : {exc}")
                raise ValidationError(
                    identifier=str(self.id),
                    message=f"Schema not valid, found '{len(exc.errors())}' error(s) in {schema_file.identifier} : {exc}",
                ) from exc

        response = await self.sdk.schema.load(
            schemas=[item.content for item in schemas_data], branch=branch_name, wait_until_converged=True
        )

        if response.errors:
            error_messages = []

            if "detail" in response.errors:
                for error in response.errors["detail"]:
                    loc_str = [str(item) for item in error["loc"][1:]]
                    error_messages.append(f"{'/'.join(loc_str)} | {error['msg']} ({error['type']})")
            elif "error" in response.errors:
                error_messages.append(f"{response.errors.get('error')}")
            else:
                error_messages.append(f"{response.errors}")

            log.error(f"Unable to load the schema : {', '.join(error_messages)}")

            raise ValidationError(
                identifier=str(self.id), message=f"Unable to load the schema : {', '.join(error_messages)}"
            )

        for schema_file in schemas_data:
            log.info(f"schema '{schema_file.identifier}' loaded successfully!")

    @task(name="import-graphql-queries", task_run_name="Import GraphQL Queries", cache_policy=NONE)  # type: ignore[arg-type]
    async def import_all_graphql_query(
        self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig
    ) -> None:
        """Search for all .gql file and import them as GraphQL query."""
        log = get_run_logger()

        commit_wt = self.get_worktree(identifier=commit)
        local_queries = {
            query.name: query.load_query(relative_path=commit_wt.directory) for query in config_file.queries
        }

        if not local_queries:
            return

        queries_in_graph = {
            query.name.value: query
            for query in await self.sdk.filters(
                kind=CoreGraphQLQuery, branch=branch_name, repository__ids=[str(self.id)]
            )
        }

        present_in_both, only_graph, only_local = compare_lists(
            list1=list(queries_in_graph.keys()), list2=list(local_queries.keys())
        )

        for query_name in only_local:
            query = local_queries[query_name]
            log.info(f"New Graphql Query {query_name!r} found, creating")
            await self.create_graphql_query(branch_name=branch_name, name=query_name, query_string=query)

        for query_name in present_in_both:
            local_query = local_queries[query_name]
            graph_query = queries_in_graph[query_name]
            if local_query != graph_query.query.value:
                log.info(f"New version of the Graphql Query {query_name!r} found, updating")
                graph_query.query.value = local_query
                await graph_query.save()

        for query_name in only_graph:
            graph_query = queries_in_graph[query_name]
            log.info(f"Graphql Query {query_name!r} not found locally, deleting")
            await graph_query.delete()

    async def create_graphql_query(self, branch_name: str, name: str, query_string: str) -> CoreGraphQLQuery:
        data = {"name": name, "query": query_string, "repository": self.id}

        schema = await self.sdk.schema.get(kind=InfrahubKind.GRAPHQLQUERY, branch=branch_name)
        create_payload = self.sdk.schema.generate_payload_create(
            schema=schema,
            data=data,
            source=self.id,
            is_protected=True,
        )
        obj = await self.sdk.create(kind=CoreGraphQLQuery, branch=branch_name, **create_payload)
        await obj.save()
        return obj

    @task(name="import-python-check-definitions", task_run_name="Import Python Check Definitions", cache_policy=NONE)  # type: ignore[arg-type]
    async def import_python_check_definitions(
        self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig
    ) -> None:
        log = get_run_logger()

        commit_wt = self.get_worktree(identifier=commit)
        branch_wt = self.get_worktree(identifier=commit or branch_name)

        # Ensure the path for this repository is present in sys.path
        if str(self.directory_root) not in sys.path:
            sys.path.append(str(self.directory_root))

        checks = []
        log.info(f"Found {len(config_file.check_definitions)} check definitions in the repository")
        for check in config_file.check_definitions:
            log.debug(f"{self.name}, file={check.file_path}")

            file_info = extract_repo_file_information(
                full_filename=branch_wt.directory / check.file_path,
                repo_directory=self.directory_root,
                worktree_directory=commit_wt.directory,
            )
            try:
                module = importlib.import_module(file_info.module_name)
            except ModuleNotFoundError as exc:
                log.warning(f"{self.name},  file={check.file_path.as_posix()} error={str(exc)}")
                raise

            checks.extend(
                await self.get_check_definition(
                    branch_name=branch_name,
                    module=module,
                    file_path=file_info.relative_path_file,
                    check_definition=check,
                )  # type: ignore[misc]
            )

        local_check_definitions = {check.name: check for check in checks}
        check_definition_in_graph = {
            check.name.value: check
            for check in await self.sdk.filters(
                kind=CoreCheckDefinition, branch=branch_name, repository__ids=[str(self.id)]
            )
        }

        present_in_both, only_graph, only_local = compare_lists(
            list1=list(check_definition_in_graph.keys()), list2=list(local_check_definitions.keys())
        )

        for check_name in only_local:
            log.info(f"New CheckDefinition {check_name!r} found, creating")
            await self.create_python_check_definition(
                branch_name=branch_name, check=local_check_definitions[check_name]
            )

        for check_name in present_in_both:
            if not await self.compare_python_check_definition(
                check=local_check_definitions[check_name],
                existing_check=check_definition_in_graph[check_name],
            ):
                log.info(f"New version of CheckDefinition {check_name!r} found, updating")
                await self.update_python_check_definition(
                    check=local_check_definitions[check_name],
                    existing_check=check_definition_in_graph[check_name],
                )

        for check_name in only_graph:
            log.info(f"CheckDefinition '{check_name!r}' not found locally, deleting")
            await check_definition_in_graph[check_name].delete()

    @task(name="import-generator-definitions", task_run_name="Import Generator Definitions", cache_policy=NONE)  # type: ignore[arg-type]
    async def import_generator_definitions(
        self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig
    ) -> None:
        log = get_run_logger()

        commit_wt = self.get_worktree(identifier=commit)
        branch_wt = self.get_worktree(identifier=commit or branch_name)

        generators = []
        log.info(f"Found {len(config_file.generator_definitions)} generator definitions in the repository")

        for generator in config_file.generator_definitions:
            log.info(f"Processing generator {generator.name} ({generator.file_path})")
            file_info = extract_repo_file_information(
                full_filename=branch_wt.directory / generator.file_path,
                repo_directory=self.directory_root,
                worktree_directory=commit_wt.directory,
            )

            generator.load_class(import_root=self.directory_root, relative_path=file_info.relative_repo_path_dir)
            generators.append(generator)

        local_generator_definitions = {generator.name: generator for generator in generators}
        generator_definition_in_graph = {
            generator.name.value: generator
            for generator in await self.sdk.filters(
                kind=CoreGeneratorDefinition, branch=branch_name, repository__ids=[str(self.id)]
            )
        }

        present_in_both, only_graph, only_local = compare_lists(
            list1=list(generator_definition_in_graph.keys()), list2=list(local_generator_definitions.keys())
        )

        for generator_name in only_local:
            log.info(f"New GeneratorDefinition {generator_name!r} found, creating")
            await self._create_generator_definition(
                branch_name=branch_name, generator=local_generator_definitions[generator_name]
            )

        for generator_name in present_in_both:
            if await self._generator_requires_update(
                generator=local_generator_definitions[generator_name],
                existing_generator=generator_definition_in_graph[generator_name],
                branch_name=branch_name,
            ):
                log.info(f"New version of GeneratorDefinition {generator_name!r} found, updating")

                await self._update_generator_definition(
                    generator=local_generator_definitions[generator_name],
                    existing_generator=generator_definition_in_graph[generator_name],
                )

        for generator_name in only_graph:
            log.info(f"GeneratorDefinition '{generator_name!r}' not found locally, deleting")
            await generator_definition_in_graph[generator_name].delete()

    async def _generator_requires_update(
        self,
        generator: InfrahubGeneratorDefinitionConfig,
        existing_generator: CoreGeneratorDefinition,
        branch_name: str,
    ) -> bool:
        graphql_queries = await self.sdk.filters(
            kind=InfrahubKind.GRAPHQLQUERY, branch=branch_name, name__value=generator.query, populate_store=True
        )
        if graphql_queries:
            generator.query = graphql_queries[0].id
        targets = await self.sdk.filters(
            kind=InfrahubKind.GENERICGROUP,
            branch=branch_name,
            name__value=generator.targets,
            populate_store=True,
            fragment=True,
        )
        if targets:
            generator.targets = targets[0].id

        if (
            existing_generator.query.id != generator.query
            or existing_generator.file_path.value != str(generator.file_path)
            or existing_generator.class_name.value != generator.class_name
            or existing_generator.parameters.value != generator.parameters
            or existing_generator.convert_query_response.value != generator.convert_query_response
            or existing_generator.targets.id != generator.targets
        ):
            return True
        return False

    @task(name="import-python-transforms", task_run_name="Import Python Transforms", cache_policy=NONE)  # type: ignore[arg-type]
    async def import_python_transforms(
        self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig
    ) -> None:
        log = get_run_logger()
        commit_wt = self.get_worktree(identifier=commit)
        branch_wt = self.get_worktree(identifier=commit or branch_name)

        # Ensure the path for this repository is present in sys.path
        if str(self.directory_root) not in sys.path:
            sys.path.append(str(self.directory_root))

        transforms: list[TransformPythonInformation] = []
        log.info(f"Found {len(config_file.python_transforms)} Python transforms in the repository")

        for transform in config_file.python_transforms:
            log.debug(f"{self.name}, file={transform.file_path}")

            file_info = extract_repo_file_information(
                full_filename=branch_wt.directory / transform.file_path,
                repo_directory=self.directory_root,
                worktree_directory=commit_wt.directory,
            )
            try:
                module = importlib.import_module(file_info.module_name)
            except ModuleNotFoundError as exc:
                log.warning(f"{self.name}, file={transform.file_path.as_posix()} error={str(exc)}")
                raise

            transforms.extend(
                await self.get_python_transforms(
                    branch_name=branch_name,
                    module=module,
                    file_path=file_info.relative_path_file,
                    transform=transform,
                )  # type: ignore[misc]
            )

        local_transform_definitions = {transform.name: transform for transform in transforms}
        transform_definition_in_graph = {
            transform.name.value: transform
            for transform in await self.sdk.filters(
                kind=CoreTransformPython, branch=branch_name, repository__ids=[str(self.id)]
            )
        }

        present_in_both, only_graph, only_local = compare_lists(
            list1=list(transform_definition_in_graph.keys()), list2=list(local_transform_definitions.keys())
        )

        for transform_name in only_local:
            log.info(f"New TransformPython {transform_name!r} found, creating")
            await self.create_python_transform(
                branch_name=branch_name, transform=local_transform_definitions[transform_name]
            )

        for transform_name in present_in_both:
            if not await self.compare_python_transform(
                local_transform=local_transform_definitions[transform_name],
                existing_transform=transform_definition_in_graph[transform_name],
            ):
                log.info(f"New version of TransformPython {transform_name!r} found, updating")
                await self.update_python_transform(
                    local_transform=local_transform_definitions[transform_name],
                    existing_transform=transform_definition_in_graph[transform_name],
                )

        for transform_name in only_graph:
            log.info(f"TransformPython {transform_name!r} not found locally, deleting")
            await transform_definition_in_graph[transform_name].delete()

    @task(name="check-definition-get", task_run_name="Get Check Definition", cache_policy=NONE)  # type: ignore[arg-type]
    async def get_check_definition(
        self,
        branch_name: str,
        module: types.ModuleType,
        file_path: str,
        check_definition: InfrahubCheckDefinitionConfig,
    ) -> list[CheckDefinitionInformation]:
        log = get_run_logger()
        if check_definition.class_name not in dir(module):
            return []

        checks = []
        check_class = getattr(module, check_definition.class_name)

        try:
            graphql_query = await self.sdk.get(
                kind=InfrahubKind.GRAPHQLQUERY, branch=branch_name, id=str(check_class.query), populate_store=True
            )
            checks.append(
                CheckDefinitionInformation(
                    name=check_definition.name,
                    repository=str(self.id),
                    class_name=check_definition.class_name,
                    check_class=check_class,
                    file_path=file_path,
                    query=str(graphql_query.id),
                    timeout=check_class.timeout,
                    parameters=check_definition.parameters,
                    targets=check_definition.targets,
                )
            )

        except Exception as exc:
            log.error(
                f"An error occurred while processing the CheckDefinition {check_class.__name__} from {file_path} : {exc} "
            )
            raise
        return checks

    @task(name="python-transform-get", task_run_name="Get Python Transform", cache_policy=NONE)  # type: ignore[arg-type]
    async def get_python_transforms(
        self, branch_name: str, module: types.ModuleType, file_path: str, transform: InfrahubPythonTransformConfig
    ) -> list[TransformPythonInformation]:
        log = get_run_logger()
        if transform.class_name not in dir(module):
            return []

        transforms = []
        transform_class = getattr(module, transform.class_name)
        graphql_query = await self.sdk.get(
            kind=InfrahubKind.GRAPHQLQUERY, branch=branch_name, id=str(transform_class.query), populate_store=True
        )
        try:
            transforms.append(
                TransformPythonInformation(
                    name=transform.name,
                    repository=str(self.id),
                    class_name=transform.class_name,
                    transform_class=transform_class,
                    file_path=file_path,
                    query=str(graphql_query.id),
                    timeout=transform_class.timeout,
                    convert_query_response=transform.convert_query_response,
                )
            )

        except Exception as exc:
            log.error(
                f"An error occurred while processing the PythonTransform {transform.name} from {file_path} : {exc} "
            )
            raise

        return transforms

    async def _create_generator_definition(
        self, generator: InfrahubGeneratorDefinitionConfig, branch_name: str
    ) -> InfrahubNode:
        data = generator.model_dump(exclude_none=True, exclude={"file_path"})
        data["file_path"] = str(generator.file_path)
        data["repository"] = self.id

        schema = await self.sdk.schema.get(kind=InfrahubKind.GENERATORDEFINITION, branch=branch_name)

        create_payload = self.sdk.schema.generate_payload_create(
            schema=schema,
            data=data,
            source=str(self.id),
            is_protected=True,
        )
        obj = await self.sdk.create(kind=InfrahubKind.GENERATORDEFINITION, branch=branch_name, **create_payload)
        await obj.save()

        return obj

    async def _update_generator_definition(
        self,
        generator: InfrahubGeneratorDefinitionConfig,
        existing_generator: CoreGeneratorDefinition,
    ) -> None:
        if existing_generator.query.id != generator.query:
            existing_generator.query = {"id": generator.query, "source": str(self.id), "is_protected": True}

        if existing_generator.class_name.value != generator.class_name:
            existing_generator.class_name.value = generator.class_name

        if existing_generator.file_path.value != str(generator.file_path):
            existing_generator.file_path.value = str(generator.file_path)

        if existing_generator.convert_query_response.value != generator.convert_query_response:
            existing_generator.convert_query_response.value = generator.convert_query_response

        if existing_generator.parameters.value != generator.parameters:
            existing_generator.parameters.value = generator.parameters

        if existing_generator.targets.id != generator.targets:
            existing_generator.targets = {"id": generator.targets, "source": str(self.id), "is_protected": True}

        await existing_generator.save()

    async def create_python_check_definition(
        self, branch_name: str, check: CheckDefinitionInformation
    ) -> CoreCheckDefinition:
        data = {
            "name": check.name,
            "repository": check.repository,
            "query": check.query,
            "file_path": check.file_path,
            "class_name": check.class_name,
            "timeout": check.timeout,
            "parameters": check.parameters,
        }

        if check.targets:
            data["targets"] = check.targets

        schema = await self.sdk.schema.get(kind=InfrahubKind.CHECKDEFINITION, branch=branch_name)

        create_payload = self.sdk.schema.generate_payload_create(
            schema=schema,
            data=data,
            source=self.id,
            is_protected=True,
        )
        obj = await self.sdk.create(kind=CoreCheckDefinition, branch=branch_name, data=create_payload)
        await obj.save()

        return obj

    async def update_python_check_definition(
        self,
        check: CheckDefinitionInformation,
        existing_check: CoreCheckDefinition,
    ) -> None:
        if existing_check.query.id != check.query:
            existing_check.query = {"id": check.query, "source": str(self.id), "is_protected": True}

        if existing_check.file_path.value != check.file_path:
            existing_check.file_path.value = check.file_path

        if existing_check.timeout.value != check.timeout:
            existing_check.timeout.value = check.timeout

        if existing_check.parameters.value != check.parameters:
            existing_check.parameters.value = check.parameters

        await existing_check.save()

    @classmethod
    async def compare_python_check_definition(
        cls, check: CheckDefinitionInformation, existing_check: CoreCheckDefinition
    ) -> bool:
        """Compare an existing Python Check Object with a Check Class
        and identify if we need to update the object in the database."""
        if (
            existing_check.query.id != check.query
            or existing_check.file_path.value != check.file_path
            or existing_check.timeout.value != check.timeout
            or existing_check.class_name.value != check.class_name
            or existing_check.parameters.value != check.parameters
        ):
            return False
        return True

    async def create_python_transform(
        self, branch_name: str, transform: TransformPythonInformation
    ) -> CoreTransformPython:
        schema = await self.sdk.schema.get(kind=InfrahubKind.TRANSFORMPYTHON, branch=branch_name)
        data = {
            "name": transform.name,
            "repository": transform.repository,
            "query": transform.query,
            "file_path": transform.file_path,
            "class_name": transform.class_name,
            "timeout": transform.timeout,
            "convert_query_response": transform.convert_query_response,
        }
        create_payload = self.sdk.schema.generate_payload_create(
            schema=schema,
            data=data,
            source=str(self.id),
            is_protected=True,
        )
        obj = await self.sdk.create(kind=CoreTransformPython, branch=branch_name, data=create_payload)
        await obj.save()
        return obj

    async def update_python_transform(
        self, existing_transform: CoreTransformPython, local_transform: TransformPythonInformation
    ) -> None:
        if existing_transform.query.id != local_transform.query:
            existing_transform.query = {"id": local_transform.query, "source": str(self.id), "is_protected": True}

        if existing_transform.file_path.value != local_transform.file_path:
            existing_transform.file_path.value = local_transform.file_path

        if existing_transform.timeout.value != local_transform.timeout:
            existing_transform.timeout.value = local_transform.timeout

        if existing_transform.convert_query_response.value != local_transform.convert_query_response:
            existing_transform.convert_query_response.value = local_transform.convert_query_response

        await existing_transform.save()

    @classmethod
    async def compare_python_transform(
        cls, existing_transform: CoreTransformPython, local_transform: TransformPythonInformation
    ) -> bool:
        if (
            existing_transform.query.id != local_transform.query
            or existing_transform.file_path.value != local_transform.file_path
            or existing_transform.timeout.value != local_transform.timeout
            or existing_transform.convert_query_response.value != local_transform.convert_query_response
        ):
            return False
        return True

    @flow(name="import-python-files", flow_run_name="Import Python file")
    async def import_all_python_files(
        self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig
    ) -> None:
        await add_tags(branches=[branch_name], nodes=[str(self.id)])

        await self.import_python_check_definitions(branch_name=branch_name, commit=commit, config_file=config_file)  # type: ignore[misc]
        await self.import_python_transforms(branch_name=branch_name, commit=commit, config_file=config_file)  # type: ignore[misc]
        await self.import_generator_definitions(branch_name=branch_name, commit=commit, config_file=config_file)  # type: ignore[misc]

    @task(name="jinja2-template-render", task_run_name="Render Jinja2 template", cache_policy=NONE)  # type: ignore[arg-type]
    async def render_jinja2_template(self, commit: str, location: str, data: dict) -> str:
        log = get_run_logger()
        commit_worktree = self.get_commit_worktree(commit=commit)

        self.validate_location(commit=commit, worktree_directory=commit_worktree.directory, file_path=location)

        jinja2_template = Jinja2Template(template=Path(location), template_directory=Path(commit_worktree.directory))
        try:
            return await jinja2_template.render(variables=data)
        except JinjaTemplateError as exc:
            log.error(str(exc), exc_info=True)
            raise TransformError(
                repository_name=self.name, commit=commit, location=location, message=exc.message
            ) from exc

    @task(name="python-check-execute", task_run_name="Execute Python Check", cache_policy=NONE)  # type: ignore[arg-type]
    async def execute_python_check(
        self,
        branch_name: str,
        commit: str,
        location: str,
        class_name: str,
        client: InfrahubClient,
        params: dict | None = None,
    ) -> InfrahubCheck:
        """Execute A Python Check stored in the repository."""
        log = get_run_logger()

        commit_worktree = self.get_commit_worktree(commit=commit)

        self.validate_location(commit=commit, worktree_directory=commit_worktree.directory, file_path=location)

        # Ensure the path for this repository is present in sys.path
        if str(self.directory_root) not in sys.path:
            sys.path.append(str(self.directory_root))

        try:
            file_info = extract_repo_file_information(
                full_filename=commit_worktree.directory / location,
                repo_directory=self.directory_root,
                worktree_directory=commit_worktree.directory,
            )

            module = importlib.import_module(file_info.module_name)

            check_class: type[InfrahubCheck] = getattr(module, class_name)

            check = check_class(
                root_directory=commit_worktree.directory, branch=branch_name, client=client, params=params
            )
            await check.run()

            return check

        except ModuleNotFoundError as exc:
            error_msg = "Unable to load the check file"
            log.error(error_msg)
            raise CheckError(
                repository_name=self.name, class_name=class_name, commit=commit, location=location, message=error_msg
            ) from exc

        except AttributeError as exc:
            error_msg = f"Unable to find the class {class_name}"
            log.error(error_msg)
            raise CheckError(
                repository_name=self.name, class_name=class_name, commit=commit, location=location, message=error_msg
            ) from exc

        except Exception as exc:
            log.critical(str(exc), exc_info=True)
            raise CheckError(
                repository_name=self.name, class_name=class_name, commit=commit, location=location, message=str(exc)
            ) from exc

    @task(name="python-transform-execute", task_run_name="Execute Python Transform", cache_policy=NONE)  # type: ignore[arg-type]
    async def execute_python_transform(
        self,
        branch_name: str,
        commit: str,
        location: str,
        client: InfrahubClient,
        convert_query_response: bool,
        data: dict | None = None,
    ) -> Any:
        """Execute A Python Transform stored in the repository."""
        log = get_run_logger()

        if "::" not in location:
            raise ValueError("Transformation location not valid, it must contains a double colons (::)")

        file_path, class_name = location.split("::")
        commit_worktree = self.get_commit_worktree(commit=commit)

        log.debug(f"Will run Python Transform from {class_name} at {location}")

        self.validate_location(commit=commit, worktree_directory=commit_worktree.directory, file_path=file_path)

        # Ensure the path for this repository is present in sys.path
        if str(self.directory_root) not in sys.path:
            sys.path.append(str(self.directory_root))

        try:
            file_info = extract_repo_file_information(
                full_filename=commit_worktree.directory / file_path,
                repo_directory=self.directory_root,
                worktree_directory=commit_worktree.directory,
            )

            module = importlib.import_module(file_info.module_name)

            transform_class: type[InfrahubTransform] = getattr(module, class_name)

            transform = transform_class(
                root_directory=commit_worktree.directory,
                branch=branch_name,
                client=client,
                convert_query_response=convert_query_response,
                infrahub_node=InfrahubNode,
            )
            return await transform.run(data=data)

        except ModuleNotFoundError as exc:
            error_msg = f"Unable to load the transform file {location}"
            log.error(error_msg)
            raise TransformError(
                repository_name=self.name, commit=commit, location=location, message=error_msg
            ) from exc

        except AttributeError as exc:
            error_msg = f"Unable to find the class {class_name} in {location}"
            log.error(error_msg)
            raise TransformError(
                repository_name=self.name, commit=commit, location=location, message=error_msg
            ) from exc

        except Exception as exc:
            log.critical(str(exc), exc_info=True)
            raise TransformError(repository_name=self.name, commit=commit, location=location, message=str(exc)) from exc

    async def artifact_generate(
        self,
        branch_name: str,
        commit: str,
        artifact: CoreArtifact,
        target: InfrahubNode,
        definition: CoreArtifactDefinition,
        transformation: CoreTransformation,
        query: CoreGraphQLQuery,
    ) -> ArtifactGenerateResult:
        """It doesn't look like this is used anywhere today ... we should either remove it or refactor render_artifact below to use this."""
        variables = target.extract(params=definition.parameters.value)
        response = await self.sdk.query_gql_query(
            name=query.name.value,
            variables=variables,
            update_group=True,
            subscribers=[artifact.id],
            tracker="artifact-query-graphql-data",
            branch_name=branch_name,
            timeout=transformation.timeout.value,
        )

        if transformation.typename == InfrahubKind.TRANSFORMJINJA2:
            artifact_content = await self.render_jinja2_template.with_options(
                timeout_seconds=transformation.timeout.value
            )(commit=commit, location=transformation.template_path.value, data=response)  # type: ignore[misc]
        elif transformation.typename == InfrahubKind.TRANSFORMPYTHON:
            transformation_location = f"{transformation.file_path.value}::{transformation.class_name.value}"
            artifact_content = await self.execute_python_transform.with_options(
                timeout_seconds=transformation.timeout.value
            )(
                branch_name=branch_name,
                commit=commit,
                location=transformation_location,
                data=response,
                client=self.sdk,
                convert_query_response=transformation.convert_query_response.value,
            )  # type: ignore[misc]

        if definition.content_type.value == ContentType.APPLICATION_JSON.value and isinstance(artifact_content, dict):
            artifact_content_str = ujson.dumps(artifact_content, indent=2)
        elif definition.content_type.value == ContentType.APPLICATION_YAML.value and isinstance(artifact_content, dict):
            artifact_content_str = yaml.dump(artifact_content, indent=2)
        else:
            artifact_content_str = str(artifact_content)

        checksum = hashlib.md5(bytes(artifact_content_str, encoding="utf-8"), usedforsecurity=False).hexdigest()

        if artifact.checksum.value == checksum:
            return ArtifactGenerateResult(
                changed=False, checksum=checksum, storage_id=artifact.storage_id.value, artifact_id=artifact.id
            )

        resp = await self.sdk.object_store.upload(content=artifact_content_str, tracker="artifact-upload-content")
        storage_id = resp["identifier"]

        artifact.checksum.value = checksum
        artifact.storage_id.value = storage_id
        artifact.status.value = ArtifactStatus.READY.value
        if artifact.name.value != definition.artifact_name.value:
            artifact.name.value = definition.artifact_name.value
        await artifact.save()

        return ArtifactGenerateResult(changed=True, checksum=checksum, storage_id=storage_id, artifact_id=artifact.id)

    async def render_artifact(
        self,
        artifact: CoreArtifact,
        artifact_created: bool,
        message: CheckArtifactCreate | RequestArtifactGenerate,
    ) -> ArtifactGenerateResult:
        response = await self.sdk.query_gql_query(
            name=message.query,
            variables=message.variables,
            update_group=True,
            subscribers=[artifact.id],
            tracker="artifact-query-graphql-data",
            branch_name=message.branch_name,
            timeout=message.timeout,
        )
        branch = registry.get_branch_from_registry(branch=message.branch_name)

        previous_checksum = artifact.checksum.value
        previous_storage_id = artifact.storage_id.value

        if message.transform_type == InfrahubKind.TRANSFORMJINJA2:
            artifact_content = await self.render_jinja2_template.with_options(timeout_seconds=message.timeout)(
                commit=message.commit, location=message.transform_location, data=response
            )  # type: ignore[misc]
        elif message.transform_type == InfrahubKind.TRANSFORMPYTHON:
            artifact_content = await self.execute_python_transform.with_options(timeout_seconds=message.timeout)(
                branch_name=message.branch_name,
                commit=message.commit,
                location=message.transform_location,
                data=response,
                client=self.sdk,
                convert_query_response=message.convert_query_response,
            )  # type: ignore[misc]

        if message.content_type == ContentType.APPLICATION_JSON.value and isinstance(artifact_content, dict):
            artifact_content_str = ujson.dumps(artifact_content, indent=2)
        elif message.content_type == ContentType.APPLICATION_YAML.value and isinstance(artifact_content, dict):
            artifact_content_str = yaml.dump(artifact_content, indent=2)
        else:
            artifact_content_str = str(artifact_content)

        checksum = hashlib.md5(bytes(artifact_content_str, encoding="utf-8"), usedforsecurity=False).hexdigest()

        if artifact.checksum.value == checksum:
            return ArtifactGenerateResult(
                changed=False, checksum=checksum, storage_id=artifact.storage_id.value, artifact_id=artifact.id
            )

        resp = await self.sdk.object_store.upload(content=artifact_content_str, tracker="artifact-upload-content")
        storage_id = resp["identifier"]

        artifact.content_type.value = message.content_type
        artifact.checksum.value = checksum
        artifact.storage_id.value = storage_id
        artifact.status.value = ArtifactStatus.READY.value
        if artifact.name.value != message.artifact_name:
            artifact.name.value = message.artifact_name
        await artifact.save()

        event_class = ArtifactCreatedEvent if artifact_created else ArtifactUpdatedEvent

        event = event_class(
            node_id=artifact.id,
            target_id=message.target_id,
            target_kind=message.target_kind,
            artifact_definition_id=message.artifact_definition,
            meta=EventMeta.from_context(context=message.context, branch=branch),
            checksum=checksum,
            checksum_previous=previous_checksum,
            storage_id=storage_id,
            storage_id_previous=previous_storage_id,
        )

        await self.service.event.send(event=event)
        return ArtifactGenerateResult(changed=True, checksum=checksum, storage_id=storage_id, artifact_id=artifact.id)
