from __future__ import annotations

import hashlib
import importlib
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Union

import jinja2
import ujson
import yaml
from infrahub_sdk import InfrahubClient  # noqa: TCH002
from infrahub_sdk.exceptions import ValidationError
from infrahub_sdk.protocols import (
    CoreArtifact,
    CoreArtifactDefinition,
    CoreCheckDefinition,
    CoreGeneratorDefinition,
    CoreGraphQLQuery,
    CoreTransformation,
    CoreTransformJinja2,
    CoreTransformPython,
)
from infrahub_sdk.schema import (
    InfrahubCheckDefinitionConfig,
    InfrahubGeneratorDefinitionConfig,
    InfrahubJinja2TransformConfig,
    InfrahubPythonTransformConfig,
    InfrahubRepositoryConfig,
)
from infrahub_sdk.utils import compare_lists
from infrahub_sdk.yaml import SchemaFile
from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError

from infrahub.core.constants import InfrahubKind, RepositorySyncStatus
from infrahub.exceptions import CheckError, TransformError
from infrahub.git.base import InfrahubRepositoryBase, extract_repo_file_information
from infrahub.log import get_logger

if TYPE_CHECKING:
    import types

    from infrahub_sdk.checks import InfrahubCheck
    from infrahub_sdk.node import InfrahubNode
    from infrahub_sdk.schema import InfrahubRepositoryArtifactDefinitionConfig
    from infrahub_sdk.transforms import InfrahubTransform

    from infrahub.message_bus import messages

# pylint: disable=too-many-lines

log = get_logger("infrahub.git")


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

    parameters: Optional[dict] = None
    """Additional Parameters to extract from each target (if targets is provided)"""

    targets: Optional[str] = Field(default=None, description="Targets if not a global check")


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


class InfrahubRepositoryIntegrator(InfrahubRepositoryBase):  # pylint: disable=too-many-public-methods
    """
    This class provides interfaces to read and process information from .infrahub.yml files and can perform
    actions for objects defined within those files.

    This class will later be broken out from the "InfrahubRepository" based classes and instead be a separate
    class that uses an "InfrahubRepository" or "InfrahubReadOnlyRepository" as input
    """

    async def import_objects_from_files(
        self, infrahub_branch_name: str, git_branch_name: Optional[str] = None, commit: Optional[str] = None
    ) -> None:
        if not commit:
            commit = self.get_commit_value(branch_name=git_branch_name or infrahub_branch_name)

        self.create_commit_worktree(commit)
        await self._update_sync_status(branch_name=infrahub_branch_name, status=RepositorySyncStatus.SYNCING)

        config_file = await self.get_repository_config(branch_name=infrahub_branch_name, commit=commit)
        sync_status = RepositorySyncStatus.IN_SYNC if config_file else RepositorySyncStatus.ERROR_IMPORT
        error: Exception | None = None

        try:
            if config_file:
                await self.import_schema_files(branch_name=infrahub_branch_name, commit=commit, config_file=config_file)

                await self.import_all_graphql_query(
                    branch_name=infrahub_branch_name, commit=commit, config_file=config_file
                )

                await self.import_all_python_files(
                    branch_name=infrahub_branch_name, commit=commit, config_file=config_file
                )
                await self.import_jinja2_transforms(
                    branch_name=infrahub_branch_name, commit=commit, config_file=config_file
                )
                await self.import_artifact_definitions(
                    branch_name=infrahub_branch_name, commit=commit, config_file=config_file
                )

        except Exception as exc:  # pylint: disable=broad-exception-caught
            sync_status = RepositorySyncStatus.ERROR_IMPORT
            error = exc

        await self._update_sync_status(branch_name=infrahub_branch_name, status=sync_status)

        if error:
            raise error

    async def _update_sync_status(self, branch_name: str, status: RepositorySyncStatus) -> None:
        update_status = """
        mutation UpdateRepositoryStatus(
            $repo_id: String!,
            $status: String!,
            ) {
            CoreGenericRepositoryUpdate(
                data: {
                    id: $repo_id,
                    sync_status: { value: $status },
                }
            ) {
                ok
            }
        }
        """

        await self.sdk.execute_graphql(
            branch_name=branch_name,
            query=update_status,
            variables={"repo_id": str(self.id), "status": status.value},
            tracker="mutation-repository-update-admin-status",
        )

    async def import_jinja2_transforms(
        self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig
    ) -> None:
        log.debug("Importing all Jinja2 transforms", repository=self.name, branch=branch_name, commit=commit)

        schema = await self.sdk.schema.get(kind=InfrahubKind.TRANSFORMJINJA2, branch=branch_name)

        transforms_in_graph = {
            transform.name.value: transform
            for transform in await self.sdk.filters(
                kind=CoreTransformJinja2, branch=branch_name, repository__ids=[str(self.id)]
            )
        }

        local_transforms: dict[str, InfrahubRepositoryJinja2] = {}

        # Process the list of local Jinja2 Transforms to organize them by name
        await self.log.info(f"Found {len(config_file.jinja2_transforms)} Jinja2 transforms in the repository")

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
            log.info(
                f"New Jinja2 Transform {transform_name!r} found, creating", repository=self.name, branch=branch_name
            )
            await self.create_jinja2_transform(branch_name=branch_name, data=local_transforms[transform_name])

        for transform_name in present_in_both:
            if not await self.compare_jinja2_transform(
                existing_transform=transforms_in_graph[transform_name], local_transform=local_transforms[transform_name]
            ):
                log.info(
                    f"New version of the Jinja2 Transform '{transform_name}' found, updating",
                    repository=self.name,
                    branch=branch_name,
                )
                await self.update_jinja2_transform(
                    existing_transform=transforms_in_graph[transform_name],
                    local_transform=local_transforms[transform_name],
                )

        for transform_name in only_graph:
            log.info(
                f"Jinja2 Transform '{transform_name}' not found locally in branch {branch_name}, deleting",
                repository=self.name,
                branch=branch_name,
            )
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
        # pylint: disable=no-member
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
        # pylint: disable=no-member
        if existing_transform.description.value != local_transform.description:
            existing_transform.description.value = local_transform.description

        if existing_transform.query.id != local_transform.query:
            existing_transform.query = {"id": local_transform.query, "source": str(self.id), "is_protected": True}

        if existing_transform.template_path.value != local_transform.template_path_value:
            existing_transform.template_path.value = local_transform.template_path_value

        await existing_transform.save()

    async def import_artifact_definitions(
        self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig
    ) -> None:
        log.debug("Importing all Artifact Definitions", repository=self.name, branch=branch_name, commit=commit)

        schema = await self.sdk.schema.get(kind=InfrahubKind.ARTIFACTDEFINITION, branch=branch_name)

        artifact_defs_in_graph = {
            artdef.name.value: artdef
            for artdef in await self.sdk.filters(kind=CoreArtifactDefinition, branch=branch_name)
        }

        local_artifact_defs: dict[str, InfrahubRepositoryArtifactDefinitionConfig] = {}

        # Process the list of local Artifact Definitions to organize them by name
        await self.log.info(f"Found {len(config_file.artifact_definitions)} artifact definitions in the repository")

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
            log.info(
                f"New Artifact Definition {artdef_name!r} found, creating", repository=self.name, branch=branch_name
            )
            await self.create_artifact_definition(branch_name=branch_name, data=local_artifact_defs[artdef_name])

        for artdef_name in present_in_both:
            if not await self.compare_artifact_definition(
                existing_artifact_definition=artifact_defs_in_graph[artdef_name],
                local_artifact_definition=local_artifact_defs[artdef_name],
            ):
                log.info(
                    f"New version of the Artifact Definition '{artdef_name}' found, updating",
                    repository=self.name,
                    branch=branch_name,
                )
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
        # pylint: disable=no-member
        if (
            existing_artifact_definition.artifact_name.value != local_artifact_definition.artifact_name
            or existing_artifact_definition.parameters.value != local_artifact_definition.parameters
            or existing_artifact_definition.content_type.value != local_artifact_definition.content_type
        ):
            return False

        return True

    async def update_artifact_definition(
        self,
        existing_artifact_definition: CoreArtifactDefinition,
        local_artifact_definition: InfrahubRepositoryArtifactDefinitionConfig,
    ) -> None:
        # pylint: disable=no-member
        if existing_artifact_definition.artifact_name.value != local_artifact_definition.artifact_name:
            existing_artifact_definition.artifact_name.value = local_artifact_definition.artifact_name

        if existing_artifact_definition.parameters.value != local_artifact_definition.parameters:
            existing_artifact_definition.parameters.value = local_artifact_definition.parameters

        if existing_artifact_definition.content_type.value != local_artifact_definition.content_type:
            existing_artifact_definition.content_type.value = local_artifact_definition.content_type

        await existing_artifact_definition.save()

    async def get_repository_config(self, branch_name: str, commit: str) -> Optional[InfrahubRepositoryConfig]:
        branch_wt = self.get_worktree(identifier=commit or branch_name)

        config_file_name = ".infrahub.yml"
        config_file = Path(os.path.join(branch_wt.directory, config_file_name))
        if not config_file.is_file():
            log.debug(
                f"Unable to find the configuration file {config_file_name}, skipping",
                repository=self.name,
                branch=branch_name,
                commit=commit,
            )
            return None

        config_file_content = config_file.read_text(encoding="utf-8")
        try:
            data = yaml.safe_load(config_file_content)
        except yaml.YAMLError as exc:
            await self.log.error(
                f"Unable to load the configuration file in YAML format {config_file_name} : {exc}",
                repository=self.name,
                branch=branch_name,
                commit=commit,
            )
            return None

        # Convert data to a dictionary to avoid it being `None` if the yaml file is just an empty document
        data = data or {}

        try:
            configuration = InfrahubRepositoryConfig(**data)
            await self.log.info(f"Successfully parsed {config_file_name}")
            return configuration
        except PydanticValidationError as exc:
            await self.log.error(
                f"Unable to load the configuration file {config_file_name}, the format is not valid  : {exc}",
                repository=self.name,
                branch=branch_name,
                commit=commit,
            )
            return None

    async def import_schema_files(self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig) -> None:
        # pylint: disable=too-many-branches
        branch_wt = self.get_worktree(identifier=commit or branch_name)

        schemas_data: list[SchemaFile] = []

        for schema in config_file.schemas:
            full_schema = Path(branch_wt.directory, schema)
            if not full_schema.exists():
                await self.log.warning(
                    f"Unable to find the schema {schema}", repository=self.name, branch=branch_name, commit=commit
                )

            if full_schema.is_file():
                schema_file = SchemaFile(identifier=str(schema), location=full_schema)
                schema_file.load_content()
                schemas_data.append(schema_file)
            elif full_schema.is_dir():
                files = await self.find_files(
                    extension=["yaml", "yml", "json"], branch_name=branch_name, commit=commit, directory=full_schema
                )
                for item in files:
                    identifier = str(item).replace(branch_wt.directory, "")
                    schema_file = SchemaFile(identifier=identifier, location=item)
                    schema_file.load_content()
                    schemas_data.append(schema_file)

        for schema_file in schemas_data:
            if schema_file.valid:
                continue
            await self.log.error(
                f"Unable to load the file {schema_file.identifier}, {schema_file.error_message}",
                repository=self.name,
                branch=branch_name,
                commit=commit,
            )

        # Valid data format of content
        for schema_file in schemas_data:
            try:
                self.sdk.schema.validate(schema_file.content)
            except PydanticValidationError as exc:
                await self.log.error(
                    f"Schema not valid, found '{len(exc.errors())}' error(s) in {schema_file.identifier} : {exc}",
                    repository=self.name,
                    branch=branch_name,
                    commit=commit,
                )
                raise ValidationError(
                    identifier=str(self.id),
                    message=f"Schema not valid, found '{len(exc.errors())}' error(s) in {schema_file.identifier} : {exc}",
                ) from exc

        response = await self.sdk.schema.load(schemas=[item.content for item in schemas_data], branch=branch_name)

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

            await self.log.error(
                f"Unable to load the schema : {', '.join(error_messages)}", repository=self.name, commit=commit
            )

            raise ValidationError(
                identifier=str(self.id), message=f"Unable to load the schema : {', '.join(error_messages)}"
            )

        for schema_file in schemas_data:
            await self.log.info(
                f"schema '{schema_file.identifier}' loaded successfully!", repository=self.name, commit=commit
            )

    async def import_all_graphql_query(
        self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig
    ) -> None:
        """Search for all .gql file and import them as GraphQL query."""

        log.debug("Importing all GraphQL Queries", repository=self.name, branch=branch_name, commit=commit)
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
            await self.log.info(
                f"New Graphql Query {query_name!r} found, creating",
                repository=self.name,
                branch=branch_name,
                commit=commit,
            )
            await self.create_graphql_query(branch_name=branch_name, name=query_name, query_string=query)

        for query_name in present_in_both:
            local_query = local_queries[query_name]
            graph_query = queries_in_graph[query_name]
            if local_query != graph_query.query.value:
                await self.log.info(
                    f"New version of the Graphql Query {query_name!r} found, updating",
                    repository=self.name,
                    branch=branch_name,
                    commit=commit,
                )
                graph_query.query.value = local_query
                await graph_query.save()

        for query_name in only_graph:
            graph_query = queries_in_graph[query_name]
            await self.log.info(
                f"Graphql Query {query_name!r} not found locally, deleting",
                repository=self.name,
                branch=branch_name,
                commit=commit,
            )
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

    async def import_python_check_definitions(
        self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig
    ) -> None:
        commit_wt = self.get_worktree(identifier=commit)
        branch_wt = self.get_worktree(identifier=commit or branch_name)

        # Ensure the path for this repository is present in sys.path
        if self.directory_root not in sys.path:
            sys.path.append(self.directory_root)

        checks = []
        await self.log.info(f"Found {len(config_file.check_definitions)} check definitions in the repository")
        for check in config_file.check_definitions:
            log.debug(self.name, import_type="check_definition", file=check.file_path)

            file_info = extract_repo_file_information(
                full_filename=os.path.join(branch_wt.directory, check.file_path.as_posix()),
                repo_directory=self.directory_root,
                worktree_directory=commit_wt.directory,
            )
            try:
                module = importlib.import_module(file_info.module_name)
            except ModuleNotFoundError as exc:
                await self.log.warning(
                    self.name, import_type="check_definition", file=check.file_path.as_posix(), error=str(exc)
                )
                raise

            checks.extend(
                await self.get_check_definition(
                    branch_name=branch_name,
                    module=module,
                    file_path=file_info.relative_path_file,
                    check_definition=check,
                )
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
            await self.log.info(
                f"New CheckDefinition {check_name!r} found, creating",
                repository=self.name,
                branch=branch_name,
                commit=commit,
            )
            await self.create_python_check_definition(
                branch_name=branch_name, check=local_check_definitions[check_name]
            )

        for check_name in present_in_both:
            if not await self.compare_python_check_definition(
                check=local_check_definitions[check_name],
                existing_check=check_definition_in_graph[check_name],
            ):
                await self.log.info(
                    f"New version of CheckDefinition {check_name!r} found, updating",
                    repository=self.name,
                    branch=branch_name,
                    commit=commit,
                )
                await self.update_python_check_definition(
                    check=local_check_definitions[check_name],
                    existing_check=check_definition_in_graph[check_name],
                )

        for check_name in only_graph:
            await self.log.info(
                f"CheckDefinition '{check_name!r}' not found locally, deleting",
                repository=self.name,
                branch=branch_name,
                commit=commit,
            )
            await check_definition_in_graph[check_name].delete()

    async def import_generator_definitions(
        self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig
    ) -> None:
        commit_wt = self.get_worktree(identifier=commit)
        branch_wt = self.get_worktree(identifier=commit or branch_name)

        generators = []
        await self.log.info(f"Found {len(config_file.generator_definitions)} generator definitions in the repository")

        for generator in config_file.generator_definitions:
            await self.log.info(f"Processing generator {generator.name} ({generator.file_path})")
            file_info = extract_repo_file_information(
                full_filename=os.path.join(branch_wt.directory, generator.file_path.as_posix()),
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
            await self.log.info(
                f"New GeneratorDefinition {generator_name!r} found, creating",
                repository=self.name,
                branch=branch_name,
                commit=commit,
            )
            await self._create_generator_definition(
                branch_name=branch_name, generator=local_generator_definitions[generator_name]
            )

        for generator_name in present_in_both:
            if await self._generator_requires_update(
                generator=local_generator_definitions[generator_name],
                existing_generator=generator_definition_in_graph[generator_name],
                branch_name=branch_name,
            ):
                await self.log.info(
                    f"New version of GeneratorDefinition {generator_name!r} found, updating",
                    repository=self.name,
                    branch=branch_name,
                    commit=commit,
                )

                await self._update_generator_definition(
                    generator=local_generator_definitions[generator_name],
                    existing_generator=generator_definition_in_graph[generator_name],
                )

        for generator_name in only_graph:
            await self.log.info(
                f"GeneratorDefinition '{generator_name!r}' not found locally, deleting",
                repository=self.name,
                branch=branch_name,
                commit=commit,
            )
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

        if (  # pylint: disable=too-many-boolean-expressions
            existing_generator.query.id != generator.query
            or existing_generator.file_path.value != str(generator.file_path)
            or existing_generator.class_name.value != generator.class_name
            or existing_generator.parameters.value != generator.parameters
            or existing_generator.convert_query_response.value != generator.convert_query_response
            or existing_generator.targets.id != generator.targets
        ):
            return True
        return False

    async def import_python_transforms(
        self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig
    ) -> None:
        commit_wt = self.get_worktree(identifier=commit)
        branch_wt = self.get_worktree(identifier=commit or branch_name)

        # Ensure the path for this repository is present in sys.path
        if self.directory_root not in sys.path:
            sys.path.append(self.directory_root)

        transforms = []
        await self.log.info(f"Found {len(config_file.python_transforms)} Python transforms in the repository")

        for transform in config_file.python_transforms:
            log.debug(self.name, import_type="python_transform", file=transform.file_path)

            file_info = extract_repo_file_information(
                full_filename=os.path.join(branch_wt.directory, transform.file_path.as_posix()),
                repo_directory=self.directory_root,
                worktree_directory=commit_wt.directory,
            )
            try:
                module = importlib.import_module(file_info.module_name)
            except ModuleNotFoundError as exc:
                await self.log.warning(
                    self.name, import_type="python_transform", file=transform.file_path.as_posix(), error=str(exc)
                )
                raise

            transforms.extend(
                await self.get_python_transforms(
                    branch_name=branch_name,
                    module=module,
                    file_path=file_info.relative_path_file,
                    transform=transform,
                )
            )

        local_transform_definitions = {transform.name: transform for transform in transforms}
        transform_definition_in_graph = {
            transform.name.value: transform
            for transform in await self.sdk.filters(
                kind=InfrahubKind.TRANSFORMPYTHON, branch=branch_name, repository__ids=[str(self.id)]
            )
        }

        present_in_both, only_graph, only_local = compare_lists(
            list1=list(transform_definition_in_graph.keys()), list2=list(local_transform_definitions.keys())
        )

        for transform_name in only_local:
            await self.log.info(
                f"New TransformPython {transform_name!r} found, creating",
                repository=self.name,
                branch=branch_name,
                commit=commit,
            )
            await self.create_python_transform(
                branch_name=branch_name, transform=local_transform_definitions[transform_name]
            )

        for transform_name in present_in_both:
            if not await self.compare_python_transform(
                local_transform=local_transform_definitions[transform_name],
                existing_transform=transform_definition_in_graph[transform_name],
            ):
                await self.log.info(
                    f"New version of TransformPython {transform_name!r} found, updating",
                    repository=self.name,
                    branch=branch_name,
                    commit=commit,
                )
                await self.update_python_transform(
                    local_transform=local_transform_definitions[transform_name],
                    existing_transform=transform_definition_in_graph[transform_name],
                )

        for transform_name in only_graph:
            await self.log.info(
                f"TransformPython {transform_name!r} not found locally, deleting",
                repository=self.name,
                branch=branch_name,
                commit=commit,
            )
            await transform_definition_in_graph[transform_name].delete()

    async def get_check_definition(
        self,
        branch_name: str,
        module: types.ModuleType,
        file_path: str,
        check_definition: InfrahubCheckDefinitionConfig,
    ) -> list[CheckDefinitionInformation]:
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

        except Exception as exc:  # pylint: disable=broad-exception-caught
            await self.log.error(
                f"An error occurred while processing the CheckDefinition {check_class.__name__} from {file_path} : {exc} ",
                repository=self.name,
                branch=branch_name,
            )
            raise
        return checks

    async def get_python_transforms(
        self, branch_name: str, module: types.ModuleType, file_path: str, transform: InfrahubPythonTransformConfig
    ) -> list[TransformPythonInformation]:
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
                )
            )

        except Exception as exc:  # pylint: disable=broad-exception-caught
            await self.log.error(
                f"An error occurred while processing the PythonTransform {transform.name} from {file_path} : {exc} ",
                repository=self.name,
                branch=branch_name,
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
        obj = await self.sdk.create(kind=CoreCheckDefinition, branch=branch_name, **create_payload)
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
        # pylint: disable=too-many-boolean-expressions
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
        }
        create_payload = self.sdk.schema.generate_payload_create(
            schema=schema,
            data=data,
            source=self.id,
            is_protected=True,
        )
        obj = await self.sdk.create(kind=CoreTransformPython, branch=branch_name, **create_payload)
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

        await existing_transform.save()

    @classmethod
    async def compare_python_transform(
        cls, existing_transform: CoreTransformPython, local_transform: TransformPythonInformation
    ) -> bool:
        if (
            existing_transform.query.id != local_transform.query
            or existing_transform.file_path.value != local_transform.file_path
            or existing_transform.timeout.value != local_transform.timeout
        ):
            return False
        return True

    async def import_all_python_files(
        self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig
    ) -> None:
        await self.import_python_check_definitions(branch_name=branch_name, commit=commit, config_file=config_file)
        await self.import_python_transforms(branch_name=branch_name, commit=commit, config_file=config_file)
        await self.import_generator_definitions(branch_name=branch_name, commit=commit, config_file=config_file)

    async def render_jinja2_template(self, commit: str, location: str, data: dict) -> str:
        commit_worktree = self.get_commit_worktree(commit=commit)

        self.validate_location(commit=commit, worktree_directory=commit_worktree.directory, file_path=location)

        try:
            templateLoader = jinja2.FileSystemLoader(searchpath=commit_worktree.directory)
            templateEnv = jinja2.Environment(loader=templateLoader, trim_blocks=True, lstrip_blocks=True)
            template = templateEnv.get_template(location)
            return template.render(**data)
        except Exception as exc:
            log.error(str(exc), exc_info=True, repository=self.name, commit=commit, location=location)
            raise TransformError(repository_name=self.name, commit=commit, location=location, message=str(exc)) from exc

    async def execute_python_check(
        self,
        branch_name: str,
        commit: str,
        location: str,
        class_name: str,
        client: InfrahubClient,
        params: Optional[dict] = None,
    ) -> InfrahubCheck:
        """Execute A Python Check stored in the repository."""

        commit_worktree = self.get_commit_worktree(commit=commit)

        self.validate_location(commit=commit, worktree_directory=commit_worktree.directory, file_path=location)

        # Ensure the path for this repository is present in sys.path
        if self.directory_root not in sys.path:
            sys.path.append(self.directory_root)

        try:
            file_info = extract_repo_file_information(
                full_filename=os.path.join(commit_worktree.directory, location),
                repo_directory=self.directory_root,
                worktree_directory=commit_worktree.directory,
            )

            module = importlib.import_module(file_info.module_name)

            check_class: InfrahubCheck = getattr(module, class_name)

            check = await check_class.init(
                root_directory=commit_worktree.directory, branch=branch_name, client=client, params=params
            )
            await check.run()

            return check

        except ModuleNotFoundError as exc:
            error_msg = "Unable to load the check file"
            log.error(error_msg, repository=self.name, branch=branch_name, commit=commit, location=location)
            raise CheckError(
                repository_name=self.name, class_name=class_name, commit=commit, location=location, message=error_msg
            ) from exc

        except AttributeError as exc:
            error_msg = f"Unable to find the class {class_name}"
            log.error(
                error_msg,
                repository=self.name,
                branch=branch_name,
                commit=commit,
                class_name=class_name,
                location=location,
            )
            raise CheckError(
                repository_name=self.name, class_name=class_name, commit=commit, location=location, message=error_msg
            ) from exc

        except Exception as exc:
            log.critical(
                str(exc),
                exc_info=True,
                repository=self.name,
                branch=branch_name,
                commit=commit,
                class_name=class_name,
                location=location,
            )
            raise CheckError(
                repository_name=self.name, class_name=class_name, commit=commit, location=location, message=str(exc)
            ) from exc

    async def execute_python_transform(
        self, branch_name: str, commit: str, location: str, client: InfrahubClient, data: Optional[dict] = None
    ) -> Any:
        """Execute A Python Transform stored in the repository."""

        if "::" not in location:
            raise ValueError("Transformation location not valid, it must contains a double colons (::)")

        file_path, class_name = location.split("::")
        commit_worktree = self.get_commit_worktree(commit=commit)

        log.debug(
            f"Will run Python Transform from {class_name} at {location}",
            repository=self.name,
            branch=branch_name,
            commit=commit,
            location=location,
        )

        self.validate_location(commit=commit, worktree_directory=commit_worktree.directory, file_path=file_path)

        # Ensure the path for this repository is present in sys.path
        if self.directory_root not in sys.path:
            sys.path.append(self.directory_root)

        try:
            file_info = extract_repo_file_information(
                full_filename=os.path.join(commit_worktree.directory, file_path),
                repo_directory=self.directory_root,
                worktree_directory=commit_worktree.directory,
            )

            module = importlib.import_module(file_info.module_name)

            transform_class: InfrahubTransform = getattr(module, class_name)

            transform = await transform_class.init(
                root_directory=commit_worktree.directory, branch=branch_name, client=client
            )
            return await transform.run(data=data)

        except ModuleNotFoundError as exc:
            error_msg = f"Unable to load the transform file {location}"
            log.error(error_msg, repository=self.name, branch=branch_name, commit=commit, location=location)
            raise TransformError(
                repository_name=self.name, commit=commit, location=location, message=error_msg
            ) from exc

        except AttributeError as exc:
            error_msg = f"Unable to find the class {class_name} in {location}"
            log.error(error_msg, repository=self.name, branch=branch_name, commit=commit, location=location)
            raise TransformError(
                repository_name=self.name, commit=commit, location=location, message=error_msg
            ) from exc

        except Exception as exc:
            log.critical(
                str(exc), exc_info=True, repository=self.name, branch=branch_name, commit=commit, location=location
            )
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
            artifact_content = await self.render_jinja2_template(
                commit=commit, location=transformation.template_path.value, data=response
            )
        elif transformation.typename == InfrahubKind.TRANSFORMPYTHON:
            transformation_location = f"{transformation.file_path.value}::{transformation.class_name.value}"
            artifact_content = await self.execute_python_transform(
                branch_name=branch_name,
                commit=commit,
                location=transformation_location,
                data=response,
                client=self.sdk,
            )

        if definition.content_type.value == "application/json":
            artifact_content_str = ujson.dumps(artifact_content, indent=2)
        elif definition.content_type.value == "text/plain":
            artifact_content_str = artifact_content

        checksum = hashlib.md5(bytes(artifact_content_str, encoding="utf-8"), usedforsecurity=False).hexdigest()

        if artifact.checksum.value == checksum:
            return ArtifactGenerateResult(
                changed=False, checksum=checksum, storage_id=artifact.storage_id.value, artifact_id=artifact.id
            )

        resp = await self.sdk.object_store.upload(content=artifact_content_str, tracker="artifact-upload-content")
        storage_id = resp["identifier"]

        artifact.checksum.value = checksum
        artifact.storage_id.value = storage_id
        artifact.status.value = "Ready"
        await artifact.save()

        return ArtifactGenerateResult(changed=True, checksum=checksum, storage_id=storage_id, artifact_id=artifact.id)

    async def render_artifact(
        self, artifact: CoreArtifact, message: Union[messages.CheckArtifactCreate, messages.RequestArtifactGenerate]
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

        if message.transform_type == InfrahubKind.TRANSFORMJINJA2:
            artifact_content = await self.render_jinja2_template(
                commit=message.commit, location=message.transform_location, data=response
            )
        elif message.transform_type == InfrahubKind.TRANSFORMPYTHON:
            artifact_content = await self.execute_python_transform(
                branch_name=message.branch_name,
                commit=message.commit,
                location=message.transform_location,
                data=response,
                client=self.sdk,
            )

        if message.content_type == "application/json":
            artifact_content_str = ujson.dumps(artifact_content, indent=2)
        elif message.content_type == "text/plain":
            artifact_content_str = artifact_content

        checksum = hashlib.md5(bytes(artifact_content_str, encoding="utf-8"), usedforsecurity=False).hexdigest()

        if artifact.checksum.value == checksum:
            return ArtifactGenerateResult(
                changed=False, checksum=checksum, storage_id=artifact.storage_id.value, artifact_id=artifact.id
            )

        resp = await self.sdk.object_store.upload(content=artifact_content_str, tracker="artifact-upload-content")
        storage_id = resp["identifier"]

        artifact.checksum.value = checksum
        artifact.storage_id.value = storage_id
        artifact.status.value = "Ready"
        await artifact.save()
        return ArtifactGenerateResult(changed=True, checksum=checksum, storage_id=storage_id, artifact_id=artifact.id)
