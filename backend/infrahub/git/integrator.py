from __future__ import annotations

import hashlib
import importlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import ujson
import yaml
from infrahub_sdk import InfrahubClient  # noqa: TC002
from infrahub_sdk.exceptions import Error as InfrahubSdkError
from infrahub_sdk.exceptions import ValidationError
from infrahub_sdk.graphql.query_renderer import render_query
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
    InfrahubWatchConfig,
)
from infrahub_sdk.schema.validate import validate_schema as validate_write_schema
from infrahub_sdk.spec.menu import MenuFile
from infrahub_sdk.spec.object import ObjectFile
from infrahub_sdk.template import Jinja2Template
from infrahub_sdk.template.exceptions import JinjaTemplateError
from infrahub_sdk.template.filters import ExecutionContext
from infrahub_sdk.utils import compare_lists
from infrahub_sdk.yaml import InfrahubFile, SchemaFile
from prefect import flow, task
from prefect.cache_policies import NONE
from prefect.logging import get_run_logger
from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError
from typing_extensions import Self

from infrahub import config, lock
from infrahub.auth.session import AnonymousSession
from infrahub.context import InfrahubContext
from infrahub.core.constants import ArtifactStatus, ContentType, InfrahubKind, RepositoryObjects, RepositorySyncStatus
from infrahub.core.registry import registry
from infrahub.events.artifact_action import ArtifactCreatedEvent, ArtifactUpdatedEvent
from infrahub.events.models import EventMeta
from infrahub.events.repository_action import CommitUpdatedEvent
from infrahub.exceptions import (
    CheckError,
    CommitNotFoundError,
    RepositoryConfigurationError,
    RepositoryInvalidFileSystemError,
    TransformError,
)
from infrahub.git.base import InfrahubRepositoryBase, extract_repo_file_information
from infrahub.git.closure_builder.dispatcher import build_default_closure_builder
from infrahub.git.fingerprint.composer import (
    ArtifactDefinitionFingerprintInput,
    FingerprintComposer,
    GeneratorDefinitionFingerprintInput,
    Jinja2TransformationFingerprintInput,
    PythonTransformationFingerprintInput,
    QueryFingerprintInput,
    build_fingerprint_composer,
)
from infrahub.log import get_logger
from infrahub.workers.dependencies import get_event_service
from infrahub.workflows.utils import add_tags

if TYPE_CHECKING:
    import types

    from infrahub_sdk.checks import InfrahubCheck
    from infrahub_sdk.ctl.utils import YamlFileVar
    from infrahub_sdk.schema import MainSchemaTypesAPI
    from infrahub_sdk.schema.repository import InfrahubRepositoryArtifactDefinitionConfig
    from infrahub_sdk.transforms import InfrahubTransform

    from infrahub.artifacts.models import CheckArtifactCreate
    from infrahub.git.closure_builder.result import ClosureResult
    from infrahub.git.models import RequestArtifactGenerate


class ArtifactGenerateResult(BaseModel):
    changed: bool
    checksum: str
    storage_id: str
    artifact_id: str


class InfrahubRepositoryJinja2(InfrahubJinja2TransformConfig):
    repository: str
    dependencies: list[str] = Field(default_factory=list)
    dependencies_complete: bool = False

    @property
    def payload(self) -> dict[str, Any]:
        # `watch` is an SDK-config-only field that drives closure detection; it is not a
        # graph attribute, so it must not reach the node create/update payload.
        data = self.model_dump(exclude_none=True, exclude={"watch"})
        data["template_path"] = self.template_path_value
        return data


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

    description: str | None = None
    """Description of the Transform"""

    watch: InfrahubWatchConfig | None = None
    """The `watch` config declared in the manifest, driving fingerprint stability."""

    dependencies: list[str] = Field(default_factory=list)
    dependencies_complete: bool = False


@dataclass
class GeneratorDefinitionWithClosure:
    """A generator definition read from disk, paired with the dependency closure computed for it.

    The closure is computed at build time while the worktree is in scope and travels with its
    config so the downstream apply step never has to recompute it or look it up by name.
    """

    config: InfrahubGeneratorDefinitionConfig
    closure: ClosureResult


@dataclass
class ObjectImportPlan:
    """The desired state of a branch's objects, built by reading the pinned commit worktree.

    Holds no graph state, only what was read from disk, so it can be built without serialization and
    then applied to the graph under the repository lock.
    """

    infrahub_branch_name: str
    commit: str
    config_file: InfrahubRepositoryConfig
    query_strings: dict[str, str]
    transform_definitions: list[TransformPythonInformation]
    jinja2_definitions: dict[str, InfrahubRepositoryJinja2]
    check_definitions: list[CheckDefinitionInformation]
    generator_definitions: list[GeneratorDefinitionWithClosure]
    artifact_definitions: dict[str, InfrahubRepositoryArtifactDefinitionConfig]


def serialize_artifact_content(
    content: Any, content_type: str, repository_name: str, commit: str, location: str
) -> str:
    """Convert the payload returned by a transform into the content stored for an artifact.

    Raises:
        TransformError: When the transform returned no payload.

    """
    if content is None:
        raise TransformError(
            repository_name=repository_name,
            commit=commit,
            location=location,
            message=f"The transform at {location} did not return a payload",
        )

    if content_type == ContentType.APPLICATION_JSON.value and isinstance(content, dict):
        return ujson.dumps(content, indent=2)
    if content_type == ContentType.APPLICATION_YAML.value and isinstance(content, dict):
        return yaml.dump(content, indent=2)

    return str(content)


class InfrahubRepositoryIntegrator(InfrahubRepositoryBase):
    """This class provides interfaces to read and process information from .infrahub.yml files and can perform.

    actions for objects defined within those files.

    This class will later be broken out from the "InfrahubRepository" based classes and instead be a separate
    class that uses an "InfrahubRepository" or "InfrahubReadOnlyRepository" as input
    """

    @classmethod
    async def init(cls, commit: str | None = None, **kwargs: Any) -> Self:
        self = cls(**kwargs)
        log = get_logger()
        try:
            self.validate_local_directories()
        except RepositoryInvalidFileSystemError:
            await self.ensure_location_is_defined()
            await self.create_locally(
                checkout_ref=await self.resolve_checkout_ref(),
                infrahub_branch_name=self.infrahub_branch_name,
                update_commit_value=False,
            )
            self.reinitialized = True
            log.info(f"Initialized the local directory for {self.name} because it was missing.")

        # An existing clone keeps whatever origin URL it was first cloned with, so re-point it when the
        # configured location has since changed, so subsequent fetches target the current remote.
        if self.location and self.has_origin:
            git_repo = self.get_git_repo_main()
            if git_repo.remotes.origin.url != self.location:
                async with lock.registry.get(name=self.name, namespace="repository"):
                    git_repo.remotes.origin.set_url(self.location)
                    await self.fetch()

        if commit:
            try:
                self.get_commit_worktree(commit=commit)
            except CommitNotFoundError:
                if not self.has_origin:
                    raise
                # The commit may exist on the remote but not yet in this worker's clone.
                # Fetch under the repository lock, which serializes shared-clone mutations, and retry.
                async with lock.registry.get(name=self.name, namespace="repository"):
                    await self.fetch()
                    self.get_commit_worktree(commit=commit)

        log.debug(
            f"Initiated the object on an existing directory for {self.name}",
        )
        return self

    async def ensure_location_is_defined(self) -> None:
        if self.location:
            return
        client = self.sdk
        repo = await client.get(
            kind=CoreGenericRepository, name__value=self.name, exclude=["tags", "credential"], raise_when_missing=True
        )
        self.location = repo.location.value

    @flow(name="import-object-from-file", flow_run_name="Import objects")
    async def import_objects_from_files(
        self, infrahub_branch_name: str, git_branch_name: str | None = None, commit: str | None = None
    ) -> None:
        plan = await self.build_import_plan(
            infrahub_branch_name=infrahub_branch_name, git_branch_name=git_branch_name, commit=commit
        )
        await self.apply_import_plan(plan)

    async def build_import_plan(
        self, infrahub_branch_name: str, git_branch_name: str | None = None, commit: str | None = None
    ) -> ObjectImportPlan:
        """Build the desired state of a branch's objects by reading the pinned commit worktree.

        Performs no graph mutation other than recording that a sync is in progress, so the expensive
        worktree reads and module imports do not need to be serialized against concurrent imports.
        """
        if not commit:
            commit = self.get_commit_value(branch_name=git_branch_name or infrahub_branch_name)

        await add_tags(branches=[infrahub_branch_name], nodes=[str(self.id)])

        self.create_commit_worktree(commit)
        await self._update_sync_status(branch_name=infrahub_branch_name, status=RepositorySyncStatus.SYNCING)

        try:
            config_file = await self.get_repository_config(branch_name=infrahub_branch_name, commit=commit)  # type: ignore[call-overload]
            query_strings = await self._build_graphql_query_definitions(commit=commit, config_file=config_file)
            transform_definitions = await self._build_python_transform_definitions(
                branch_name=infrahub_branch_name, commit=commit, config_file=config_file
            )
            jinja2_definitions = await self._build_jinja2_transform_definitions(
                branch_name=infrahub_branch_name, commit=commit, config_file=config_file
            )
            check_definitions = await self._build_python_check_definitions(
                branch_name=infrahub_branch_name, commit=commit, config_file=config_file
            )
            generator_definitions = await self._build_generator_definitions(
                branch_name=infrahub_branch_name, commit=commit, config_file=config_file
            )
            artifact_definitions = await self._build_artifact_definitions(
                branch_name=infrahub_branch_name, config_file=config_file
            )
        except Exception:
            await self._update_sync_status(branch_name=infrahub_branch_name, status=RepositorySyncStatus.ERROR_IMPORT)
            raise

        return ObjectImportPlan(
            infrahub_branch_name=infrahub_branch_name,
            commit=commit,
            config_file=config_file,
            query_strings=query_strings,
            transform_definitions=transform_definitions,
            jinja2_definitions=jinja2_definitions,
            check_definitions=check_definitions,
            generator_definitions=generator_definitions,
            artifact_definitions=artifact_definitions,
        )

    async def apply_import_plan(self, plan: ObjectImportPlan) -> None:
        """Apply a previously built plan to the graph: schema, queries, transforms, objects, definitions.

        Performs every graph mutation of the import, so it must run serialized against any concurrent
        import of the same repository.
        """
        sync_status = RepositorySyncStatus.IN_SYNC
        error: Exception | None = None

        # A single composer instance is threaded through every phase so a dependent
        # definition composes the fingerprint freshly computed for its inputs in the
        # same import, in dependency order: queries, then transformations and generator
        # definitions, then artifact definitions.
        fingerprint_composer = self._build_fingerprint_composer(commit=plan.commit)

        try:
            await self.import_schema_files(
                branch_name=plan.infrahub_branch_name, commit=plan.commit, config_file=plan.config_file
            )  # type: ignore[call-overload]
            if plan.config_file.schemas:
                await self.sdk.schema.all(branch=plan.infrahub_branch_name, refresh=True)
            await self._apply_graphql_query_definitions(
                branch_name=plan.infrahub_branch_name,
                local_queries=plan.query_strings,
                fingerprint_composer=fingerprint_composer,
            )
            # Transforms must be registered before objects so that an object referencing a transform
            # defined in the same repository resolves during import.
            await self._apply_python_transform_definitions(
                branch_name=plan.infrahub_branch_name,
                definitions=plan.transform_definitions,
                fingerprint_composer=fingerprint_composer,
            )
            await self._apply_jinja2_transform_definitions(
                branch_name=plan.infrahub_branch_name,
                local_transforms=plan.jinja2_definitions,
                fingerprint_composer=fingerprint_composer,
            )
            await self.import_objects(
                branch_name=plan.infrahub_branch_name,
                commit=plan.commit,
                config_file=plan.config_file,
            )  # type: ignore[call-overload]
            # Checks, generators and artifact definitions are imported after objects because their
            # targets reference groups that are defined as objects in the repository.
            await self._apply_python_check_definitions(
                branch_name=plan.infrahub_branch_name, definitions=plan.check_definitions
            )
            await self._apply_generator_definitions(
                branch_name=plan.infrahub_branch_name,
                definitions=plan.generator_definitions,
                fingerprint_composer=fingerprint_composer,
            )
            await self._apply_artifact_definitions(
                branch_name=plan.infrahub_branch_name,
                local_artifact_defs=plan.artifact_definitions,
                fingerprint_composer=fingerprint_composer,
            )
            # Generator actions and trigger rules are imported last: they reference the definitions
            # created above, which in turn reference groups imported as objects, forming a cycle a
            # single objects pass cannot satisfy on a first import.
            await self.import_deferred_objects(
                branch_name=plan.infrahub_branch_name,
                commit=plan.commit,
                config_file=plan.config_file,
            )  # type: ignore[call-overload]

        except Exception as exc:
            sync_status = RepositorySyncStatus.ERROR_IMPORT
            error = exc

        await self._update_sync_status(branch_name=plan.infrahub_branch_name, status=sync_status)

        if error:
            raise error

        if self.reinitialized:
            return

        infrahub_branch = registry.get_branch_from_registry(branch=plan.infrahub_branch_name)
        event_context = InfrahubContext.init(branch=infrahub_branch, account=AnonymousSession()).to_event_context()
        event_service = await get_event_service()
        await event_service.send(
            CommitUpdatedEvent(
                commit=plan.commit,
                repository_name=self.name,
                repository_id=str(self.id),
                meta=EventMeta(branch=infrahub_branch, context=event_context),
            )
        )

    def _build_fingerprint_composer(self, commit: str) -> FingerprintComposer:
        """Wire a fingerprint composer against the pinned commit worktree for one import."""
        return build_fingerprint_composer(repo=self.get_git_repo_worktree(identifier=commit), commit=commit)

    @task(name="import-jinja2-transforms", task_run_name="Import Jinja2 transform", cache_policy=NONE)
    async def import_jinja2_transforms(
        self,
        branch_name: str,
        commit: str,
        config_file: InfrahubRepositoryConfig,
    ) -> None:
        local_transforms = await self._build_jinja2_transform_definitions(
            branch_name=branch_name, commit=commit, config_file=config_file
        )
        await self._apply_jinja2_transform_definitions(
            branch_name=branch_name,
            local_transforms=local_transforms,
            fingerprint_composer=self._build_fingerprint_composer(commit=commit),
        )

    async def _build_jinja2_transform_definitions(
        self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig
    ) -> dict[str, InfrahubRepositoryJinja2]:
        """Build the desired Jinja2 transform definitions from the repository config.

        Performs no graph mutation, so it does not need to be serialized against concurrent imports.
        """
        log = get_run_logger()

        schema = await self.sdk.schema.get(kind=InfrahubKind.TRANSFORMJINJA2, branch=branch_name)
        worktree = self.get_worktree(identifier=commit or branch_name)

        local_transforms: dict[str, InfrahubRepositoryJinja2] = {}

        # Process the list of local Jinja2 Transforms to organize them by name
        log.info(f"Found {len(config_file.jinja2_transforms)} Jinja2 transforms in the repository")

        closure_builder = build_default_closure_builder(logger=log)

        for config_transform in config_file.jinja2_transforms:
            try:
                self.sdk.schema.validate_data_against_schema(
                    schema=schema, data=config_transform.model_dump(exclude_none=True, exclude={"watch"})
                )
            except PydanticValidationError as exc:
                for error in exc.errors():
                    locations = [str(error_location) for error_location in error["loc"]]
                    log.error(f"  {'/'.join(locations)} | {error['msg']} ({error['type']})")
                continue
            except ValidationError as exc:
                log.error(exc.message)
                continue

            closure = closure_builder.build(
                transform_config=config_transform,
                worktree_root=Path(worktree.directory),
            )

            transform = InfrahubRepositoryJinja2(
                repository=str(self.id),
                dependencies=list(closure.dependencies),
                dependencies_complete=closure.complete,
                **config_transform.model_dump(),
            )
            local_transforms[transform.name] = transform

        return local_transforms

    async def _apply_jinja2_transform_definitions(
        self,
        branch_name: str,
        local_transforms: dict[str, InfrahubRepositoryJinja2],
        fingerprint_composer: FingerprintComposer,
    ) -> None:
        """Reconcile the desired Jinja2 transform definitions against the graph: create, update, delete.

        Mutates graph nodes whose names are globally unique, so it must run serialized against any
        concurrent import of the same repository.
        """
        log = get_run_logger()

        # Compose the fingerprint while the query reference is still the query name, so the
        # connected query's freshly-computed fingerprint can be looked up in the registry.
        transform_fingerprints = {
            transform.name: fingerprint_composer.compose_transformation(
                Jinja2TransformationFingerprintInput(
                    name=transform.name,
                    query_name=str(transform.query),
                    dependencies=tuple(transform.dependencies),
                    dependencies_complete=transform.dependencies_complete,
                    watch=transform.watch,
                    template_path=transform.template_path_value,
                )
            )
            for transform in local_transforms.values()
        }

        # Resolve each query reference to its node id now that the queries have been applied.
        for transform in local_transforms.values():
            graphql_query = await self.sdk.get(
                kind=InfrahubKind.GRAPHQLQUERY, branch=branch_name, id=str(transform.query), populate_store=True
            )
            transform.query = graphql_query.id

        transforms_in_graph = {
            transform.name.value: transform
            for transform in await self.sdk.filters(
                kind=CoreTransformJinja2, branch=branch_name, repository__ids=[str(self.id)]
            )
        }

        present_in_both, only_graph, only_local = compare_lists(
            list1=list(transforms_in_graph.keys()), list2=list(local_transforms.keys())
        )

        for transform_name in only_local:
            log.info(f"New Jinja2 Transform {transform_name!r} found, creating")
            await self.create_jinja2_transform(
                branch_name=branch_name,
                data=local_transforms[transform_name],
                fingerprint=transform_fingerprints[transform_name],
            )

        for transform_name in present_in_both:
            existing_transform = transforms_in_graph[transform_name]
            fingerprint = transform_fingerprints[transform_name]
            unchanged = await self.compare_jinja2_transform(
                existing_transform=existing_transform, local_transform=local_transforms[transform_name]
            )
            if not unchanged or existing_transform.fingerprint.value != fingerprint:
                log.info(f"New version of the Jinja2 Transform '{transform_name}' found, updating")
                await self.update_jinja2_transform(
                    existing_transform=existing_transform,
                    local_transform=local_transforms[transform_name],
                    fingerprint=fingerprint,
                )

        for transform_name in only_graph:
            log.info(f"Jinja2 Transform '{transform_name}' not found locally in branch {branch_name}, deleting")
            await transforms_in_graph[transform_name].delete()

    async def create_jinja2_transform(
        self, branch_name: str, data: InfrahubRepositoryJinja2, fingerprint: str | None = None
    ) -> CoreTransformJinja2:
        schema = await self.sdk.schema.get(kind=InfrahubKind.TRANSFORMJINJA2, branch=branch_name)
        payload_data = {**data.payload, "fingerprint": fingerprint}
        create_payload = self.sdk.schema.generate_payload_create(
            schema=schema, data=payload_data, source=self.id, is_protected=True
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
            or existing_transform.template_path.value != str(local_transform.template_path)
            or existing_transform.query.id != local_transform.query
            or existing_transform.dependencies.value != local_transform.dependencies
            or existing_transform.dependencies_complete.value != local_transform.dependencies_complete
        ):
            return False

        return True

    async def update_jinja2_transform(
        self,
        existing_transform: CoreTransformJinja2,
        local_transform: InfrahubRepositoryJinja2,
        fingerprint: str | None = None,
    ) -> None:
        if fingerprint is not None and existing_transform.fingerprint.value != fingerprint:
            existing_transform.fingerprint.value = fingerprint

        if existing_transform.description.value != local_transform.description:
            existing_transform.description.value = local_transform.description

        if existing_transform.query.id != local_transform.query:
            existing_transform.query = {"id": local_transform.query, "source": str(self.id), "is_protected": True}

        if existing_transform.template_path.value != local_transform.template_path_value:
            existing_transform.template_path.value = local_transform.template_path_value

        if existing_transform.dependencies.value != local_transform.dependencies:
            existing_transform.dependencies.value = local_transform.dependencies

        if existing_transform.dependencies_complete.value != local_transform.dependencies_complete:
            existing_transform.dependencies_complete.value = local_transform.dependencies_complete

        await existing_transform.save()

    @task(name="import-artifact-definitions", task_run_name="Import Artifact Definitions", cache_policy=NONE)
    async def import_artifact_definitions(
        self,
        branch_name: str,
        commit: str,
        config_file: InfrahubRepositoryConfig,
    ) -> None:
        local_artifact_defs = await self._build_artifact_definitions(branch_name=branch_name, config_file=config_file)
        await self._apply_artifact_definitions(
            branch_name=branch_name,
            local_artifact_defs=local_artifact_defs,
            fingerprint_composer=self._build_fingerprint_composer(commit=commit),
        )

    async def _build_artifact_definitions(
        self, branch_name: str, config_file: InfrahubRepositoryConfig
    ) -> dict[str, InfrahubRepositoryArtifactDefinitionConfig]:
        """Build the desired artifact definitions from the repository config.

        Performs no graph mutation, so it does not need to be serialized against concurrent imports.
        """
        log = get_run_logger()
        schema = await self.sdk.schema.get(kind=InfrahubKind.ARTIFACTDEFINITION, branch=branch_name)

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

        return local_artifact_defs

    async def _apply_artifact_definitions(
        self,
        branch_name: str,
        local_artifact_defs: dict[str, InfrahubRepositoryArtifactDefinitionConfig],
        fingerprint_composer: FingerprintComposer,
    ) -> None:
        """Reconcile the desired artifact definitions against the graph by creating and updating.

        Mutates graph nodes whose names are globally unique, so it must run serialized against any
        concurrent import of the same repository.
        """
        log = get_run_logger()

        artifact_fingerprints = {
            artdef_name: fingerprint_composer.compose_artifact_definition(
                ArtifactDefinitionFingerprintInput(
                    name=artdef_name,
                    transformation_name=artdef.transformation,
                    parameters=artdef.parameters,
                    content_type=artdef.content_type,
                    artifact_name=artdef.artifact_name,
                    target_group_id=await self._resolve_target_group_id(
                        branch_name=branch_name, group_name=artdef.targets
                    ),
                )
            )
            for artdef_name, artdef in local_artifact_defs.items()
        }

        artifact_defs_in_graph = {
            artdef.name.value: artdef
            for artdef in await self.sdk.filters(
                kind=CoreArtifactDefinition, branch=branch_name, prefetch_relationships=True, populate_store=True
            )
        }

        present_in_both, _, only_local = compare_lists(
            list1=list(artifact_defs_in_graph.keys()), list2=list(local_artifact_defs.keys())
        )

        for artdef_name in only_local:
            log.info(f"New Artifact Definition {artdef_name!r} found, creating")
            await self.create_artifact_definition(
                branch_name=branch_name,
                data=local_artifact_defs[artdef_name],
                fingerprint=artifact_fingerprints[artdef_name],
            )

        for artdef_name in present_in_both:
            existing_artifact_definition = artifact_defs_in_graph[artdef_name]
            fingerprint = artifact_fingerprints[artdef_name]
            unchanged = await self.compare_artifact_definition(
                existing_artifact_definition=existing_artifact_definition,
                local_artifact_definition=local_artifact_defs[artdef_name],
            )
            if not unchanged or existing_artifact_definition.fingerprint.value != fingerprint:
                log.info(f"New version of the Artifact Definition '{artdef_name}' found, updating")
                await self.update_artifact_definition(
                    existing_artifact_definition=existing_artifact_definition,
                    local_artifact_definition=local_artifact_defs[artdef_name],
                    fingerprint=fingerprint,
                )

    async def create_artifact_definition(
        self,
        branch_name: str,
        data: InfrahubRepositoryArtifactDefinitionConfig,
        fingerprint: str | None = None,
    ) -> InfrahubNode:
        schema = await self.sdk.schema.get(kind=InfrahubKind.ARTIFACTDEFINITION, branch=branch_name)
        payload_data = {**data.model_dump(), "fingerprint": fingerprint}
        create_payload = self.sdk.schema.generate_payload_create(
            schema=schema, data=payload_data, source=self.id, is_protected=True
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
        fingerprint: str | None = None,
    ) -> None:
        if fingerprint is not None and existing_artifact_definition.fingerprint.value != fingerprint:
            existing_artifact_definition.fingerprint.value = fingerprint

        if existing_artifact_definition.artifact_name.value != local_artifact_definition.artifact_name:
            existing_artifact_definition.artifact_name.value = local_artifact_definition.artifact_name

        if existing_artifact_definition.parameters.value != local_artifact_definition.parameters:
            existing_artifact_definition.parameters.value = local_artifact_definition.parameters

        if existing_artifact_definition.content_type.value != local_artifact_definition.content_type:
            existing_artifact_definition.content_type.value = local_artifact_definition.content_type

        if existing_artifact_definition.targets.peer.name.value != local_artifact_definition.targets:
            existing_artifact_definition.targets = local_artifact_definition.targets

        await existing_artifact_definition.save()

    @task(name="repository-get-config", task_run_name="get repository config", cache_policy=NONE)
    async def get_repository_config(self, branch_name: str, commit: str) -> InfrahubRepositoryConfig:
        """Load and parse the repository configuration file.

        Args:
            branch_name: The name of the branch to load the config from.
            commit: The commit hash to load the config from.

        Returns:
            The parsed repository configuration.

        Raises:
            RepositoryConfigurationError: If the configuration file is missing,
                cannot be parsed as YAML, or has an invalid format.

        """
        branch_wt = self.get_worktree(identifier=commit or branch_name)
        log = get_run_logger()

        # Check for both .infrahub.yml and .infrahub.yaml, prefer .yml if both exist
        config_file_yml = branch_wt.directory / ".infrahub.yml"
        config_file_yaml = branch_wt.directory / ".infrahub.yaml"

        if config_file_yml.is_file():
            config_file = config_file_yml
            config_file_name = ".infrahub.yml"
        elif config_file_yaml.is_file():
            config_file = config_file_yaml
            config_file_name = ".infrahub.yaml"
        else:
            log.error(
                f"Repository '{self.name}' is missing a configuration file. "
                "Expected '.infrahub.yml' or '.infrahub.yaml' in the repository root."
            )
            raise RepositoryConfigurationError(
                identifier=self.name,
                message=f"Repository '{self.name}' is missing a configuration file. "
                f"Please add a '.infrahub.yml' or '.infrahub.yaml' file to the repository root. "
                f"See https://docs.infrahub.app/topics/repository for more information.",
            )

        config_file_content = config_file.read_text(encoding="utf-8")
        try:
            data = yaml.safe_load(config_file_content)
        except yaml.YAMLError as exc:
            log.error(f"Unable to load the configuration file in YAML format {config_file_name}: {exc}")
            raise RepositoryConfigurationError(
                identifier=self.name,
                message=f"Repository '{self.name}' has an invalid configuration file '{config_file_name}'. "
                f"The file could not be parsed as valid YAML: {exc}",
            ) from exc

        # Convert data to a dictionary to avoid it being `None` if the yaml file is just an empty document
        data = data or {}

        try:
            configuration = InfrahubRepositoryConfig(**data)
            log.info(f"Successfully parsed {config_file_name}")
            return configuration
        except PydanticValidationError as exc:
            log.error(f"Unable to load the configuration file {config_file_name}, the format is not valid: {exc}")
            raise RepositoryConfigurationError(
                identifier=self.name,
                message=f"Repository '{self.name}' has an invalid configuration file '{config_file_name}'. "
                f"The file format is not valid: {exc}",
            ) from exc

    @task(name="import-schema-files", task_run_name="Import schema files", cache_policy=NONE)
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
            result = validate_write_schema(schema=schema_file.content or {})
            for warning in result.warnings:
                log.warning(f"{schema_file.identifier}: {warning.message}")
            if not result.valid:
                message = (
                    f"Schema not valid, found '{len(result.errors)}' error(s) in "
                    f"{schema_file.identifier} : {'; '.join(result.messages)}"
                )
                log.error(message)
                raise ValidationError(identifier=str(self.id), message=message)

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

    @task(name="import-graphql-queries", task_run_name="Import GraphQL Queries", cache_policy=NONE)
    async def import_all_graphql_query(
        self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig
    ) -> None:
        """Search for all .gql file and import them as GraphQL query.

        Raises:
            Error: When rendering a configured GraphQL query template fails (from infrahub_sdk).

        """
        local_queries = await self._build_graphql_query_definitions(commit=commit, config_file=config_file)
        await self._apply_graphql_query_definitions(
            branch_name=branch_name,
            local_queries=local_queries,
            fingerprint_composer=self._build_fingerprint_composer(commit=commit),
        )

    async def _build_graphql_query_definitions(
        self, commit: str, config_file: InfrahubRepositoryConfig
    ) -> dict[str, str]:
        """Render the desired GraphQL queries from the pinned commit worktree.

        Performs no graph mutation, so it does not need to be serialized against concurrent imports.

        Raises:
            Error: When rendering a configured GraphQL query template fails (from infrahub_sdk).

        """
        log = get_run_logger()

        commit_wt = self.get_worktree(identifier=commit)

        local_queries: dict[str, str] = {}
        for query_config in config_file.queries:
            try:
                local_queries[query_config.name] = render_query(
                    name=query_config.name,
                    config=config_file,
                    relative_path=str(commit_wt.directory),
                )
            except InfrahubSdkError as exc:
                log.error(f"Query '{query_config.name}': {exc}")
                raise

        return local_queries

    async def _apply_graphql_query_definitions(
        self, branch_name: str, local_queries: dict[str, str], fingerprint_composer: FingerprintComposer
    ) -> None:
        """Reconcile the desired GraphQL queries against the graph by creating, updating and deleting.

        Mutates graph nodes whose names are globally unique, so it must run serialized against any
        concurrent import of the same repository.
        """
        log = get_run_logger()

        # Every local query fingerprint is computed and registered so a transformation or
        # generator importing later in the same run reads the freshly-computed value, even
        # for queries whose text is unchanged and whose node is therefore not re-saved.
        query_fingerprints = {
            query_name: fingerprint_composer.compose_query(
                QueryFingerprintInput(name=query_name, query_text=query_text)
            )
            for query_name, query_text in local_queries.items()
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
            await self.create_graphql_query(
                branch_name=branch_name, name=query_name, query_string=query, fingerprint=query_fingerprints[query_name]
            )

        for query_name in present_in_both:
            local_query = local_queries[query_name]
            graph_query = queries_in_graph[query_name]
            fingerprint = query_fingerprints[query_name]
            changed = False
            if local_query != graph_query.query.value:
                log.info(f"New version of the Graphql Query {query_name!r} found, updating")
                graph_query.query.value = local_query
                changed = True
            if graph_query.fingerprint.value != fingerprint:
                graph_query.fingerprint.value = fingerprint
                changed = True
            if changed:
                await graph_query.save()

        for query_name in only_graph:
            graph_query = queries_in_graph[query_name]
            log.info(f"Graphql Query {query_name!r} not found locally, deleting")
            await graph_query.delete()

    async def create_graphql_query(
        self, branch_name: str, name: str, query_string: str, fingerprint: str | None = None
    ) -> CoreGraphQLQuery:
        data = {"name": name, "query": query_string, "repository": self.id, "fingerprint": fingerprint}

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

    @task(name="import-python-check-definitions", task_run_name="Import Python Check Definitions", cache_policy=NONE)
    async def import_python_check_definitions(
        self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig
    ) -> None:
        definitions = await self._build_python_check_definitions(
            branch_name=branch_name, commit=commit, config_file=config_file
        )
        await self._apply_python_check_definitions(branch_name=branch_name, definitions=definitions)

    async def _build_python_check_definitions(
        self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig
    ) -> list[CheckDefinitionInformation]:
        """Build the desired check definitions by reading the pinned commit worktree.

        Performs no graph mutation, so it does not need to be serialized against concurrent imports.

        Raises:
            ModuleNotFoundError: When a check module cannot be imported.

        """
        log = get_run_logger()

        commit_wt = self.get_worktree(identifier=commit)
        branch_wt = self.get_worktree(identifier=commit or branch_name)

        # Ensure the path for this repository is present in sys.path
        if str(self.directory_root) not in sys.path:
            sys.path.append(str(self.directory_root))

        checks: list[CheckDefinitionInformation] = []
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
                    module=module,
                    file_path=file_info.relative_path_file,
                    check_definition=check,
                )  # type: ignore[call-overload]
            )

        return checks

    async def _apply_python_check_definitions(
        self, branch_name: str, definitions: list[CheckDefinitionInformation]
    ) -> None:
        """Reconcile the desired check definitions against the graph by creating, updating and deleting.

        Mutates graph nodes whose names are globally unique, so it must run serialized against any
        concurrent import of the same repository.
        """
        log = get_run_logger()

        local_check_definitions = {check.name: check for check in definitions}

        # Resolve each query reference to its node id now that the queries have been applied.
        for check in local_check_definitions.values():
            graphql_query = await self.sdk.get(
                kind=InfrahubKind.GRAPHQLQUERY, branch=branch_name, id=str(check.query), populate_store=True
            )
            check.query = str(graphql_query.id)

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

    @task(name="import-generator-definitions", task_run_name="Import Generator Definitions", cache_policy=NONE)
    async def import_generator_definitions(
        self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig
    ) -> None:
        definitions = await self._build_generator_definitions(
            branch_name=branch_name, commit=commit, config_file=config_file
        )
        await self._apply_generator_definitions(
            branch_name=branch_name,
            definitions=definitions,
            fingerprint_composer=self._build_fingerprint_composer(commit=commit),
        )

    async def _build_generator_definitions(
        self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig
    ) -> list[GeneratorDefinitionWithClosure]:
        """Build the desired generator definitions by reading the pinned commit worktree.

        Each returned item pairs a generator config with the dependency closure computed for it.
        The closure is computed here because the worktree is only in scope at build time; the
        downstream apply/create/update steps consume it from the paired information object.

        Performs no graph mutation, so it does not need to be serialized against concurrent imports.
        """
        log = get_run_logger()

        commit_wt = self.get_worktree(identifier=commit)
        branch_wt = self.get_worktree(identifier=commit or branch_name)

        generators: list[GeneratorDefinitionWithClosure] = []
        log.info(f"Found {len(config_file.generator_definitions)} generator definitions in the repository")

        closure_builder = build_default_closure_builder(logger=log)

        for generator in config_file.generator_definitions:
            log.info(f"Processing generator {generator.name} ({generator.file_path})")
            file_info = extract_repo_file_information(
                full_filename=branch_wt.directory / generator.file_path,
                repo_directory=self.directory_root,
                worktree_directory=commit_wt.directory,
            )

            generator.load_class(import_root=self.directory_root, relative_path=file_info.relative_repo_path_dir)

            closure = closure_builder.build(
                transform_config=generator,
                worktree_root=Path(branch_wt.directory),
            )
            generators.append(GeneratorDefinitionWithClosure(config=generator, closure=closure))

        return generators

    async def _apply_generator_definitions(
        self,
        branch_name: str,
        definitions: list[GeneratorDefinitionWithClosure],
        fingerprint_composer: FingerprintComposer,
    ) -> None:
        """Reconcile the desired generator definitions against the graph by creating, updating and deleting.

        Mutates graph nodes whose names are globally unique, so it must run serialized against any
        concurrent import of the same repository.
        """
        log = get_run_logger()

        local_generator_definitions = {definition.config.name: definition for definition in definitions}

        # Compose fingerprints before the query/target references are resolved to node ids,
        # while the config still carries the query name used for the registry lookup.
        generator_fingerprints = {
            generator_name: fingerprint_composer.compose_generator_definition(
                GeneratorDefinitionFingerprintInput(
                    name=generator_name,
                    query_name=str(definition.config.query),
                    dependencies=tuple(definition.closure.dependencies),
                    dependencies_complete=definition.closure.complete,
                    watch=definition.config.watch,
                    parameters=definition.config.parameters,
                    class_name=definition.config.class_name,
                    convert_query_response=definition.config.convert_query_response,
                    target_group_id=await self._resolve_target_group_id(
                        branch_name=branch_name, group_name=definition.config.targets
                    ),
                )
            )
            for generator_name, definition in local_generator_definitions.items()
        }

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
            definition = local_generator_definitions[generator_name]
            await self._create_generator_definition(
                branch_name=branch_name,
                generator=definition.config,
                closure=definition.closure,
                fingerprint=generator_fingerprints[generator_name],
            )

        for generator_name in present_in_both:
            definition = local_generator_definitions[generator_name]
            existing_generator = generator_definition_in_graph[generator_name]
            fingerprint = generator_fingerprints[generator_name]
            requires_update = await self._generator_requires_update(
                generator=definition.config,
                existing_generator=existing_generator,
                branch_name=branch_name,
                closure=definition.closure,
            )
            if requires_update or existing_generator.fingerprint.value != fingerprint:
                log.info(f"New version of GeneratorDefinition {generator_name!r} found, updating")

                await self._update_generator_definition(
                    generator=definition.config,
                    existing_generator=existing_generator,
                    closure=definition.closure,
                    fingerprint=fingerprint,
                )

        for generator_name in only_graph:
            log.info(f"GeneratorDefinition '{generator_name!r}' not found locally, deleting")
            await generator_definition_in_graph[generator_name].delete()

    async def _resolve_target_group_id(self, branch_name: str, group_name: str) -> str | None:
        """Resolve a target group name to its node id for the group-identity fingerprint term."""
        targets = await self.sdk.filters(
            kind=InfrahubKind.GENERICGROUP,
            branch=branch_name,
            name__value=group_name,
            populate_store=True,
            fragment=True,
        )
        return targets[0].id if targets else None

    async def _generator_requires_update(
        self,
        generator: InfrahubGeneratorDefinitionConfig,
        existing_generator: CoreGeneratorDefinition,
        branch_name: str,
        closure: ClosureResult,
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
            or existing_generator.execute_in_proposed_change.value != generator.execute_in_proposed_change
            or existing_generator.execute_after_merge.value != generator.execute_after_merge
            or existing_generator.dependencies.value != list(closure.dependencies)
            or existing_generator.dependencies_complete.value != closure.complete
        ):
            return True
        return False

    @task(name="import-python-transforms", task_run_name="Import Python Transforms", cache_policy=NONE)
    async def import_python_transforms(
        self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig
    ) -> None:
        definitions = await self._build_python_transform_definitions(
            branch_name=branch_name, commit=commit, config_file=config_file
        )
        await self._apply_python_transform_definitions(
            branch_name=branch_name,
            definitions=definitions,
            fingerprint_composer=self._build_fingerprint_composer(commit=commit),
        )

    async def _build_python_transform_definitions(
        self, branch_name: str, commit: str, config_file: InfrahubRepositoryConfig
    ) -> list[TransformPythonInformation]:
        """Build the desired transform definitions by reading the pinned commit worktree.

        Performs no graph mutation, so it does not need to be serialized against concurrent imports.

        Raises:
            ModuleNotFoundError: When a transform module cannot be imported.

        """
        log = get_run_logger()
        commit_wt = self.get_worktree(identifier=commit)
        branch_wt = self.get_worktree(identifier=commit or branch_name)

        # Ensure the path for this repository is present in sys.path
        if str(self.directory_root) not in sys.path:
            sys.path.append(str(self.directory_root))

        transforms: list[TransformPythonInformation] = []
        log.info(f"Found {len(config_file.python_transforms)} Python transforms in the repository")

        closure_builder = build_default_closure_builder(logger=log)

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

            closure = closure_builder.build(
                transform_config=transform,
                worktree_root=Path(branch_wt.directory),
            )

            transforms.extend(
                await self.get_python_transforms(
                    module=module,
                    file_path=file_info.relative_path_file,
                    transform=transform,
                    dependencies=list(closure.dependencies),
                    dependencies_complete=closure.complete,
                )  # type: ignore[call-overload]
            )

        return transforms

    async def _apply_python_transform_definitions(
        self,
        branch_name: str,
        definitions: list[TransformPythonInformation],
        fingerprint_composer: FingerprintComposer,
    ) -> None:
        """Reconcile the desired transform definitions against the graph by creating, updating and deleting.

        Mutates graph nodes whose names are globally unique, so it must run serialized against any
        concurrent import of the same repository.
        """
        log = get_run_logger()
        local_transform_definitions = {transform.name: transform for transform in definitions}

        # Compose the fingerprint while the query reference is still the query name, so the
        # connected query's freshly-computed fingerprint can be looked up in the registry.
        transform_fingerprints = {
            transform.name: fingerprint_composer.compose_transformation(
                PythonTransformationFingerprintInput(
                    name=transform.name,
                    query_name=str(transform.query),
                    dependencies=tuple(transform.dependencies),
                    dependencies_complete=transform.dependencies_complete,
                    watch=transform.watch,
                    class_name=transform.class_name,
                    convert_query_response=transform.convert_query_response,
                )
            )
            for transform in local_transform_definitions.values()
        }

        # Resolve each query reference to its node id now that the queries have been applied.
        for transform in local_transform_definitions.values():
            graphql_query = await self.sdk.get(
                kind=InfrahubKind.GRAPHQLQUERY, branch=branch_name, id=str(transform.query), populate_store=True
            )
            transform.query = str(graphql_query.id)

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
                branch_name=branch_name,
                transform=local_transform_definitions[transform_name],
                fingerprint=transform_fingerprints[transform_name],
            )

        for transform_name in present_in_both:
            existing_transform = transform_definition_in_graph[transform_name]
            fingerprint = transform_fingerprints[transform_name]
            unchanged = await self.compare_python_transform(
                local_transform=local_transform_definitions[transform_name],
                existing_transform=existing_transform,
            )
            if not unchanged or existing_transform.fingerprint.value != fingerprint:
                log.info(f"New version of TransformPython {transform_name!r} found, updating")
                await self.update_python_transform(
                    local_transform=local_transform_definitions[transform_name],
                    existing_transform=existing_transform,
                    fingerprint=fingerprint,
                )

        for transform_name in only_graph:
            log.info(f"TransformPython {transform_name!r} not found locally, deleting")
            await transform_definition_in_graph[transform_name].delete()

    async def _load_yamlfile_from_disk(self, paths: list[Path], file_type: type[YamlFileVar]) -> list[YamlFileVar]:
        data_files = file_type.load_from_disk(paths=paths)

        for data_file in data_files:
            if not data_file.valid or not data_file.content:
                raise ValueError(f"{data_file.error_message} ({data_file.location})")

        return data_files

    @staticmethod
    def _object_depends_on_definitions(schema: MainSchemaTypesAPI) -> bool:
        """Whether an object of this kind references a definition created later in the import.

        Generator actions and trigger rules point at a generator definition that the import
        creates from a dedicated config section, so they must be reconciled after those
        definitions rather than alongside the groups the definitions target.
        """
        return bool({InfrahubKind.ACTION, InfrahubKind.TRIGGERRULE}.intersection(schema.inherit_from))

    async def _load_objects(
        self,
        paths: list[Path],
        branch: str,
        file_type: type[InfrahubFile],
        defer: bool | None = None,
    ) -> None:
        """Load one or multiple objects files into Infrahub.

        ``defer`` selects which documents to load by their reconciliation ordering: ``False``
        loads the documents that do not depend on repository-defined definitions, ``True`` loads
        the generator actions and trigger rules that reference such a definition, and ``None``
        loads every document.

        Raises:
            ValueError: When a referenced schema lacks both ``human_friendly_id`` and ``default_filter``.

        """
        log = get_run_logger()
        files = await self._load_yamlfile_from_disk(paths=paths, file_type=file_type)

        selected = []
        for file in files:
            if defer is not None:
                file.validate_content()
                schema = await self.sdk.schema.get(kind=file.spec.kind, branch=branch)
                if self._object_depends_on_definitions(schema=schema) is not defer:
                    continue
            selected.append(file)

        for file in selected:
            await file.validate_format(client=self.sdk, branch=branch)
            schema = await self.sdk.schema.get(kind=file.spec.kind, branch=branch)
            if not schema.human_friendly_id and not schema.default_filter:
                raise ValueError(
                    f"Schemas of objects or menus defined within {file.location} "
                    "should have a `human_friendly_id` defined to avoid creating duplicated objects."
                )

        for file in selected:
            log.info(f"Loading objects defined in {file.location}")
            await file.process(client=self.sdk, branch=branch)

    async def _import_file_paths(
        self,
        branch_name: str,
        commit: str,
        files_pathes: list[Path],
        object_type: RepositoryObjects,
        defer: bool | None = None,
        tracking_suffix: str = "",
    ) -> None:
        branch_wt = self.get_worktree(identifier=commit or branch_name)
        file_pathes = [branch_wt.directory / file_path for file_path in files_pathes]

        # A tracking_suffix isolates a subset of the same object_type in its own group so its
        # delete_unused reconciliation does not remove members tracked by the other subset.
        # We currently assume there can't be concurrent imports, but if so, we might need to clone the client before tracking here.
        async with self.sdk.start_tracking(
            identifier=f"group-repo-{object_type.value}{tracking_suffix}-{self.id}",
            delete_unused_nodes=True,
            branch=branch_name,
            group_type="CoreRepositoryGroup",
            group_params={"content": object_type.value, "repository": str(self.id)},
        ):
            file_type = repo_object_type_to_file_type(object_type)
            await self._load_objects(
                paths=file_pathes,
                branch=branch_name,
                file_type=file_type,
                defer=defer,
            )

    @task(name="import-objects", task_run_name="Import Objects", cache_policy=NONE)
    async def import_objects(
        self,
        branch_name: str,
        commit: str,
        config_file: InfrahubRepositoryConfig,
    ) -> None:
        await self._import_file_paths(
            branch_name=branch_name,
            commit=commit,
            files_pathes=config_file.objects,
            object_type=RepositoryObjects.OBJECT,
            defer=False,
        )
        await self._import_file_paths(
            branch_name=branch_name,
            commit=commit,
            files_pathes=config_file.menus,
            object_type=RepositoryObjects.MENU,
        )

    @task(name="import-deferred-objects", task_run_name="Import Deferred Objects", cache_policy=NONE)
    async def import_deferred_objects(
        self,
        branch_name: str,
        commit: str,
        config_file: InfrahubRepositoryConfig,
    ) -> None:
        """Import the objects that reference definitions created earlier in the import.

        Generator actions and trigger rules resolve mandatory relationships to definitions the
        import creates from dedicated config sections, so they are reconciled here, after those
        definitions exist, in a tracking group of their own so reconciling them does not delete
        the objects imported before the definitions.
        """
        await self._import_file_paths(
            branch_name=branch_name,
            commit=commit,
            files_pathes=config_file.objects,
            object_type=RepositoryObjects.OBJECT,
            defer=True,
            tracking_suffix="-deferred",
        )

    @task(name="check-definition-get", task_run_name="Get Check Definition", cache_policy=NONE)
    async def get_check_definition(
        self,
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
            checks.append(
                CheckDefinitionInformation(
                    name=check_definition.name,
                    repository=str(self.id),
                    class_name=check_definition.class_name,
                    check_class=check_class,
                    file_path=file_path,
                    query=str(check_class.query),
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

    @task(name="python-transform-get", task_run_name="Get Python Transform", cache_policy=NONE)
    async def get_python_transforms(
        self,
        module: types.ModuleType,
        file_path: str,
        transform: InfrahubPythonTransformConfig,
        dependencies: list[str],
        dependencies_complete: bool,
    ) -> list[TransformPythonInformation]:
        log = get_run_logger()
        if transform.class_name not in dir(module):
            return []

        transforms = []
        transform_class = getattr(module, transform.class_name)
        try:
            transforms.append(
                TransformPythonInformation(
                    name=transform.name,
                    repository=str(self.id),
                    class_name=transform.class_name,
                    transform_class=transform_class,
                    file_path=file_path,
                    query=str(transform_class.query),
                    timeout=transform_class.timeout,
                    convert_query_response=transform.convert_query_response,
                    description=transform.description,
                    watch=transform.watch,
                    dependencies=dependencies,
                    dependencies_complete=dependencies_complete,
                )
            )

        except Exception as exc:
            log.error(
                f"An error occurred while processing the PythonTransform {transform.name} from {file_path} : {exc} "
            )
            raise

        return transforms

    async def _create_generator_definition(
        self,
        generator: InfrahubGeneratorDefinitionConfig,
        branch_name: str,
        closure: ClosureResult,
        fingerprint: str | None = None,
    ) -> InfrahubNode:
        # `watch` is an SDK-config-only field that drives closure detection; it is not a
        # graph attribute, so it must not reach the node create payload.
        data = generator.model_dump(exclude_none=True, exclude={"file_path", "watch"})
        data["file_path"] = str(generator.file_path)
        data["repository"] = self.id
        data["dependencies"] = list(closure.dependencies)
        data["dependencies_complete"] = closure.complete
        data["fingerprint"] = fingerprint

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
        closure: ClosureResult,
        fingerprint: str | None = None,
    ) -> None:
        if fingerprint is not None and existing_generator.fingerprint.value != fingerprint:
            existing_generator.fingerprint.value = fingerprint

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

        if existing_generator.execute_in_proposed_change.value != generator.execute_in_proposed_change:
            existing_generator.execute_in_proposed_change.value = generator.execute_in_proposed_change

        if existing_generator.execute_after_merge.value != generator.execute_after_merge:
            existing_generator.execute_after_merge.value = generator.execute_after_merge

        if existing_generator.dependencies.value != list(closure.dependencies):
            existing_generator.dependencies.value = list(closure.dependencies)

        if existing_generator.dependencies_complete.value != closure.complete:
            existing_generator.dependencies_complete.value = closure.complete

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
        """Compare an existing Python Check Object with a Check Class.

        and identify if we need to update the object in the database.

        """
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
        self, branch_name: str, transform: TransformPythonInformation, fingerprint: str | None = None
    ) -> CoreTransformPython:
        schema = await self.sdk.schema.get(kind=InfrahubKind.TRANSFORMPYTHON, branch=branch_name)
        data = {
            "name": transform.name,
            "description": transform.description,
            "repository": transform.repository,
            "query": transform.query,
            "file_path": transform.file_path,
            "class_name": transform.class_name,
            "timeout": transform.timeout,
            "convert_query_response": transform.convert_query_response,
            "dependencies": transform.dependencies,
            "dependencies_complete": transform.dependencies_complete,
            "fingerprint": fingerprint,
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
        self,
        existing_transform: CoreTransformPython,
        local_transform: TransformPythonInformation,
        fingerprint: str | None = None,
    ) -> None:
        if fingerprint is not None and existing_transform.fingerprint.value != fingerprint:
            existing_transform.fingerprint.value = fingerprint

        if existing_transform.description.value != local_transform.description:
            existing_transform.description.value = local_transform.description

        if existing_transform.query.id != local_transform.query:
            existing_transform.query = {"id": local_transform.query, "source": str(self.id), "is_protected": True}

        if existing_transform.file_path.value != local_transform.file_path:
            existing_transform.file_path.value = local_transform.file_path

        if existing_transform.timeout.value != local_transform.timeout:
            existing_transform.timeout.value = local_transform.timeout

        if existing_transform.convert_query_response.value != local_transform.convert_query_response:
            existing_transform.convert_query_response.value = local_transform.convert_query_response

        if existing_transform.dependencies.value != local_transform.dependencies:
            existing_transform.dependencies.value = local_transform.dependencies

        if existing_transform.dependencies_complete.value != local_transform.dependencies_complete:
            existing_transform.dependencies_complete.value = local_transform.dependencies_complete

        await existing_transform.save()

    @classmethod
    async def compare_python_transform(
        cls, existing_transform: CoreTransformPython, local_transform: TransformPythonInformation
    ) -> bool:
        if (
            existing_transform.description.value != local_transform.description
            or existing_transform.query.id != local_transform.query
            or existing_transform.file_path.value != local_transform.file_path
            or existing_transform.timeout.value != local_transform.timeout
            or existing_transform.convert_query_response.value != local_transform.convert_query_response
            or existing_transform.dependencies.value != local_transform.dependencies
            or existing_transform.dependencies_complete.value != local_transform.dependencies_complete
        ):
            return False
        return True

    @task(name="jinja2-template-render", task_run_name="Render Jinja2 template", cache_policy=NONE)
    async def render_jinja2_template(self, commit: str, location: str, data: dict) -> str:
        log = get_run_logger()
        commit_worktree = self.get_commit_worktree(commit=commit)

        self.validate_location(commit=commit, worktree_directory=commit_worktree.directory, file_path=location)

        jinja2_template = Jinja2Template(
            template=Path(location), template_directory=Path(commit_worktree.directory), client=self.sdk
        )
        try:
            context = ExecutionContext.CORE | ExecutionContext.WORKER
            if not config.SETTINGS.security.restrict_untrusted_jinja2_filters:
                context = ExecutionContext.ALL
            jinja2_template.validate(context=context)
            return await jinja2_template.render(variables=data)
        except JinjaTemplateError as exc:
            log.error(str(exc), exc_info=True)
            raise TransformError(
                repository_name=self.name, commit=commit, location=location, message=exc.message
            ) from exc

    @task(name="python-check-execute", task_run_name="Execute Python Check", cache_policy=NONE)
    async def execute_python_check(
        self,
        branch_name: str,
        commit: str,
        location: str,
        class_name: str,
        client: InfrahubClient,
        params: dict | None = None,
    ) -> InfrahubCheck:
        """Execute A Python Check stored in the repository.

        Raises:
            CheckError: When the check module cannot be loaded, the class is missing or running the check raises an unexpected exception.

        """
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

    @task(name="python-transform-execute", task_run_name="Execute Python Transform", cache_policy=NONE)
    async def execute_python_transform(
        self,
        branch_name: str,
        commit: str,
        location: str,
        client: InfrahubClient,
        convert_query_response: bool,
        data: dict | None = None,
    ) -> Any:
        """Execute A Python Transform stored in the repository.

        Raises:
            ValueError: When ``location`` does not contain the expected ``module::class`` separator.
            TransformError: When the transform module cannot be loaded, the class is missing or running the transform raises an unexpected exception.

        """
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
        variables = await target.extract(params=definition.parameters.value)
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
            transformation_location = transformation.template_path.value
            artifact_content = await self.render_jinja2_template.with_options(
                timeout_seconds=transformation.timeout.value
            )(commit=commit, location=transformation_location, data=response)  # type: ignore[call-overload]
        elif transformation.typename == InfrahubKind.TRANSFORMPYTHON:
            transformation_location = f"{transformation.file_path.value}::{transformation.class_name.value}"
            artifact_content = await self.execute_python_transform.with_options(
                timeout_seconds=transformation.timeout.value
            )(
                client=self.sdk,
                branch_name=branch_name,
                commit=commit,
                location=transformation_location,
                data=response,
                convert_query_response=transformation.convert_query_response.value,
            )  # type: ignore[call-overload]

        artifact_content_str = serialize_artifact_content(
            content=artifact_content,
            content_type=definition.content_type.value,
            repository_name=self.name,
            commit=commit,
            location=transformation_location,
        )

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
            name=message.query_id,
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
            )  # type: ignore[call-overload]
        elif message.transform_type == InfrahubKind.TRANSFORMPYTHON:
            artifact_content = await self.execute_python_transform.with_options(timeout_seconds=message.timeout)(
                client=self.sdk,
                branch_name=message.branch_name,
                commit=message.commit,
                location=message.transform_location,
                data=response,
                convert_query_response=message.convert_query_response,
            )  # type: ignore[call-overload]

        artifact_content_str = serialize_artifact_content(
            content=artifact_content,
            content_type=message.content_type,
            repository_name=self.name,
            commit=message.commit,
            location=message.transform_location,
        )

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
        await artifact.save(request_context=message.context.to_request_context())

        event_class = ArtifactCreatedEvent if artifact_created else ArtifactUpdatedEvent
        event_context = message.context.to_event_context()

        event = event_class(
            node_id=artifact.id,
            target_id=message.target_id,
            target_kind=message.target_kind,
            artifact_definition_id=message.artifact_definition,
            artifact_definition_name=message.artifact_definition_name,
            meta=EventMeta.from_context(context=event_context, branch=branch),
            checksum=checksum,
            checksum_previous=previous_checksum,
            storage_id=storage_id,
            storage_id_previous=previous_storage_id,
        )

        event_service = await get_event_service()
        await event_service.send(event=event)
        return ArtifactGenerateResult(changed=True, checksum=checksum, storage_id=storage_id, artifact_id=artifact.id)


def repo_object_type_to_file_type(repo_object: RepositoryObjects) -> type[InfrahubFile]:
    match repo_object:
        case RepositoryObjects.OBJECT:
            return ObjectFile
        case RepositoryObjects.MENU:
            return MenuFile
        case _:
            raise ValueError(f"Unknown repository object type: {repo_object}")
