from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import patch
from uuid import UUID

import pytest

from infrahub.core.branch.enums import BranchStatus
from infrahub.core.branch.models import Branch
from infrahub.core.convert_object_type.object_conversion import ConversionFieldInput, ConversionFieldValue
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.query.delete import DeleteAfterTimeQuery
from infrahub.core.timestamp import Timestamp
from infrahub.git import InfrahubReadOnlyRepository, InfrahubRepository
from tests.constants.kind import PERSON
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClient

from typing import TYPE_CHECKING

from infrahub.core.constants import GLOBAL_BRANCH_NAME, InfrahubKind
from infrahub.core.manager import NodeManager
from tests.helpers.file_repo import FileRepo
from tests.helpers.schema import CAR_SCHEMA, load_schema

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient

    from infrahub.core.protocols import CoreGenericRepository, CoreReadOnlyRepository, CoreRepository
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubServices


CONVERSION_RESPONSE_COMMON_FIELDS = {
    "name": {"is_mandatory": True, "source_field_name": "name", "relationship_cardinality": None},
    "description": {
        "is_mandatory": False,
        "source_field_name": "description",
        "relationship_cardinality": None,
    },
    "location": {
        "is_mandatory": True,
        "source_field_name": "location",
        "relationship_cardinality": None,
    },
    "internal_status": {
        "is_mandatory": False,
        "source_field_name": "internal_status",
        "relationship_cardinality": None,
    },
    "operational_status": {
        "is_mandatory": False,
        "source_field_name": "operational_status",
        "relationship_cardinality": None,
    },
    "sync_status": {
        "is_mandatory": False,
        "source_field_name": "sync_status",
        "relationship_cardinality": None,
    },
    "credential": {
        "is_mandatory": False,
        "source_field_name": "credential",
        "relationship_cardinality": "one",
    },
    "tags": {"is_mandatory": False, "source_field_name": "tags", "relationship_cardinality": "many"},
    "transformations": {
        "is_mandatory": False,
        "source_field_name": "transformations",
        "relationship_cardinality": "many",
    },
    "queries": {
        "is_mandatory": False,
        "source_field_name": "queries",
        "relationship_cardinality": "many",
    },
    "checks": {
        "is_mandatory": False,
        "source_field_name": "checks",
        "relationship_cardinality": "many",
    },
    "generators": {
        "is_mandatory": False,
        "source_field_name": "generators",
        "relationship_cardinality": "many",
    },
    "groups_objects": {
        "is_mandatory": False,
        "source_field_name": "groups_objects",
        "relationship_cardinality": "many",
    },
    "member_of_groups": {
        "is_mandatory": False,
        "source_field_name": "member_of_groups",
        "relationship_cardinality": "many",
    },
    "subscriber_of_groups": {
        "is_mandatory": False,
        "source_field_name": "subscriber_of_groups",
        "relationship_cardinality": "many",
    },
}


class TestConvertRepository(TestInfrahubApp):
    @pytest.fixture(scope="class")
    async def local_repo(
        self, db: InfrahubDatabase, git_repos_source_dir_module_scope: Path, git_repos_dir_module_scope: Path
    ) -> None:
        await load_schema(db, schema=CAR_SCHEMA)
        FileRepo(name="car-dealership", sources_directory=git_repos_source_dir_module_scope)

        # It seems mandatory to create some data before creating infrahub repo
        john = await Node.init(schema=PERSON, db=db)
        await john.new(db=db, name="John", height=175, description="The famous Joe Doe")
        await john.save(db=db)

        people = await Node.init(schema=InfrahubKind.STANDARDGROUP, db=db)
        await people.new(db=db, name="people", members=[john])
        await people.save(db=db)

    async def test_convert_repo_to_read_only(
        self,
        client: InfrahubClient,
        schemas_conversion: dict,
        db: InfrahubDatabase,
        initialize_registry: None,
        service: InfrahubServices,
        default_branch: Branch,
        git_repos_source_dir_module_scope: Path,
        local_repo: None,
    ) -> None:
        """
        First build fields mapping required to convert a CoreRepository to a CoreReadOnlyRepository,
        then convert the repository, and finally check that the repository is working properly.
        """

        start_time = Timestamp()

        query = """ query($source_kind: String!, $target_kind: String!) {
                FieldsMappingTypeConversion(source_kind: $source_kind, target_kind: $target_kind) {
                    mapping
                }
            }
            """

        conversion_response = await client.execute_graphql(
            query=query,
            variables={
                "branch": default_branch.name,
                "source_kind": "CoreRepository",
                "target_kind": "CoreReadOnlyRepository",
            },
            branch_name=default_branch.name,
        )

        assert conversion_response == {
            "FieldsMappingTypeConversion": {
                "mapping": {
                    **CONVERSION_RESPONSE_COMMON_FIELDS,
                    "ref": {"is_mandatory": False, "source_field_name": None, "relationship_cardinality": None},
                    "commit": {"is_mandatory": False, "source_field_name": "commit", "relationship_cardinality": None},
                }
            }
        }

        with patch("infrahub.git.tasks.lock"):
            client_repository = await client.create(
                kind=InfrahubKind.REPOSITORY,
                data={"name": "car-dealership", "location": f"{git_repos_source_dir_module_scope}/car-dealership"},
            )
            await client_repository.save()

        repository: CoreRepository = await NodeManager.get_one(
            db=db, id=client_repository.id, kind=InfrahubKind.REPOSITORY, raise_on_error=True
        )
        assert repository.commit.value
        assert repository.internal_status.value == "active"
        assert repository.operational_status.value == "online"

        # We want to test unidirectional relationship coming from validators towards a repository,
        # so we create a proposed change that would create validators attached to this repo.
        branch_2_name = "branch_2"
        _ = await create_branch(branch_name=branch_2_name, db=db)
        await self._create_proposed_change_and_wait_for_validators(
            repository_id=repository.id,
            client=client,
            source_branch=branch_2_name,
            target_branch=default_branch.name,
            db=db,
        )

        query = """
            mutation($node_id: String!, $target_kind: String!, $fields_mapping: GenericScalar!) {
                ConvertObjectType(data: {
                        node_id: $node_id,
                        target_kind: $target_kind,
                        fields_mapping: $fields_mapping
                    }) {
                        ok
                        node
                }
            }
        """

        # Reconstruct fields mapping to use for the convert object type endpoint
        mapping = {}
        for field_name, field_infos in conversion_response["FieldsMappingTypeConversion"]["mapping"].items():
            if field_infos["source_field_name"] is not None:
                mapping[field_name] = ConversionFieldInput(source_field=field_infos["source_field_name"])
            else:
                assert field_name == "ref"

        mapping["ref"] = ConversionFieldInput(data=ConversionFieldValue(attribute_value=repository.commit.value))
        mapping_dict = {field_name: model.model_dump(mode="json") for field_name, model in mapping.items()}

        with patch("infrahub.git.tasks.lock"):
            conversion_response = await client.execute_graphql(
                query=query,
                variables={
                    "branch": default_branch.name,
                    "node_id": str(repository.id),
                    "fields_mapping": mapping_dict,
                    "target_kind": "CoreReadOnlyRepository",
                },
            )
        assert conversion_response["ConvertObjectType"]["ok"] is True
        res_node = conversion_response["ConvertObjectType"]["node"]
        assert res_node["__kind__"] == "CoreReadOnlyRepository"

        new_repo_id = conversion_response["ConvertObjectType"]["node"]["id"]
        read_only_repo = await NodeManager.get_one(db=db, id=new_repo_id, raise_on_error=True)

        # Now make sure repository has been correctly initialized
        repo_intern = InfrahubReadOnlyRepository(  # type: ignore[call-arg]
            id=UUID(read_only_repo.id),
            name=read_only_repo.name.value,
            location=read_only_repo.location.value,
            client=service.client,
            ref=read_only_repo.ref.value,
            infrahub_branch_name=default_branch.name,
            service=service,
        )
        repo_intern.validate_local_directories()

        await self._validate_repo_groups(db=db, repository=repository)

        await self._validate_branches_status(
            db=db, branch_2_name=branch_2_name, default_branch_name=default_branch.name
        )

        await self._validate_rebase(
            branch_name=branch_2_name,
            client=client,
            db=db,
            new_repo_id=new_repo_id,
            original_commit=repository.commit.value,
        )

        query_delete = await DeleteAfterTimeQuery.init(db=db, timestamp=start_time)
        await query_delete.execute(db=db)

    async def test_convert_read_only_to_read_write(
        self,
        client: InfrahubClient,
        schemas_conversion: dict,
        db: InfrahubDatabase,
        initialize_registry: None,
        service: InfrahubServices,
        default_branch: Branch,
        local_repo: None,
        git_repos_source_dir_module_scope: Path,
    ) -> None:
        """
        First build fields mapping required to convert a CoreReadOnlyRepository to a CoreRepository,
        then convert the repository, and finally check that the repository is working properly.
        """

        start_time = Timestamp()

        query_get_mapping = """ query($source_kind: String!, $target_kind: String!) {
                FieldsMappingTypeConversion(source_kind: $source_kind, target_kind: $target_kind) {
                    mapping
                }
            }
            """

        conversion_response = await client.execute_graphql(
            query=query_get_mapping,
            variables={
                "source_kind": "CoreReadOnlyRepository",
                "target_kind": "CoreRepository",
            },
            branch_name=default_branch.name,
        )

        assert conversion_response == {
            "FieldsMappingTypeConversion": {
                "mapping": {
                    **CONVERSION_RESPONSE_COMMON_FIELDS,
                    "default_branch": {
                        "is_mandatory": False,
                        "source_field_name": None,
                        "relationship_cardinality": None,
                    },
                    "commit": {"is_mandatory": False, "source_field_name": "commit", "relationship_cardinality": None},
                }
            }
        }

        # Create a read-only repository and convert it to read-write

        with patch("infrahub.git.tasks.lock"):
            client_repository = await client.create(
                kind=InfrahubKind.READONLYREPOSITORY,
                data={"name": "car-dealership", "location": f"{git_repos_source_dir_module_scope}/car-dealership"},
            )
            await client_repository.save()

        repository: CoreReadOnlyRepository = await NodeManager.get_one(
            db=db, id=client_repository.id, kind=InfrahubKind.READONLYREPOSITORY, raise_on_error=True
        )

        assert repository.commit.value
        assert repository.internal_status.value == "active"

        # We want to test unidirectional relationship coming from validators towards a repository,
        # so we create a proposed change that would create validators attached to this repo.
        branch_2_name = "branch_2"
        _ = await create_branch(branch_name=branch_2_name, db=db)
        await self._create_proposed_change_and_wait_for_validators(
            repository_id=repository.id,
            client=client,
            source_branch=branch_2_name,
            target_branch=default_branch.name,
            db=db,
        )

        query_convert_repo = """
            mutation($node_id: String!, $target_kind: String!, $fields_mapping: GenericScalar!) {
                ConvertObjectType(data: {
                        node_id: $node_id,
                        target_kind: $target_kind,
                        fields_mapping: $fields_mapping
                    }) {
                        ok
                        node
                }
            }
        """

        # Reconstruct fields mapping to use for the convert object type endpoint
        mapping = {}
        for field_name, field_infos in conversion_response["FieldsMappingTypeConversion"]["mapping"].items():
            if field_infos["source_field_name"] is not None:
                mapping[field_name] = ConversionFieldInput(source_field=field_infos["source_field_name"])
            else:
                assert field_name == "default_branch"

        mapping["default_branch"] = ConversionFieldInput(data=ConversionFieldValue(attribute_value=default_branch.name))
        mapping_dict = {field_name: model.model_dump(mode="json") for field_name, model in mapping.items()}

        with patch("infrahub.git.tasks.lock"):
            conversion_response = await client.execute_graphql(
                query=query_convert_repo,
                variables={
                    "branch": default_branch.name,
                    "node_id": str(repository.id),
                    "fields_mapping": mapping_dict,
                    "target_kind": "CoreRepository",
                },
            )

        assert conversion_response["ConvertObjectType"]["ok"] is True
        res_node = conversion_response["ConvertObjectType"]["node"]
        assert res_node["__kind__"] == "CoreRepository"

        new_repo_id = conversion_response["ConvertObjectType"]["node"]["id"]
        read_write_repo = await NodeManager.get_one(db=db, id=new_repo_id, raise_on_error=True)

        await self._validate_read_write_repo_init(branch=default_branch, repository=read_write_repo, service=service)

        await self._validate_repo_groups(db=db, repository=repository)

        await self._validate_branches_status(
            db=db, branch_2_name=branch_2_name, default_branch_name=default_branch.name
        )

        await self._validate_rebase(
            branch_name=branch_2_name,
            client=client,
            db=db,
            new_repo_id=new_repo_id,
            original_commit=repository.commit.value,
        )

        query_delete = await DeleteAfterTimeQuery.init(db=db, timestamp=start_time)
        await query_delete.execute(db=db)

    async def _validate_rebase(
        self, branch_name: str, client: InfrahubClient, db: InfrahubDatabase, new_repo_id: str, original_commit: str
    ):
        success = await client.branch.rebase(branch_name=branch_name)
        assert success is True
        repo_branch_after_rebase = await NodeManager.get_one(
            db=db,
            id=new_repo_id,
            raise_on_error=True,
            branch=branch_name,
        )
        assert repo_branch_after_rebase.commit.value == original_commit

    async def test_convert_to_read_write_on_main_create_branch_before(
        self,
        client: InfrahubClient,
        schemas_conversion: dict,
        db: InfrahubDatabase,
        initialize_registry: None,
        service: InfrahubServices,
        default_branch: Branch,
        local_repo: None,
        git_repos_source_dir_module_scope: Path,
    ) -> None:
        """
        First build fields mapping required to convert a CoreReadOnlyRepository to a CoreRepository,
        then convert the repository, and finally check that the repository is working properly.
        """

        start_time = Timestamp()

        query_get_mapping = """ query($source_kind: String!, $target_kind: String!) {
                FieldsMappingTypeConversion(source_kind: $source_kind, target_kind: $target_kind) {
                    mapping
                }
            }
            """

        conversion_response = await client.execute_graphql(
            query=query_get_mapping,
            variables={
                "source_kind": "CoreReadOnlyRepository",
                "target_kind": "CoreRepository",
            },
            branch_name=default_branch.name,
        )

        assert conversion_response == {
            "FieldsMappingTypeConversion": {
                "mapping": {
                    **CONVERSION_RESPONSE_COMMON_FIELDS,
                    "default_branch": {
                        "is_mandatory": False,
                        "source_field_name": None,
                        "relationship_cardinality": None,
                    },
                    "commit": {"is_mandatory": False, "source_field_name": "commit", "relationship_cardinality": None},
                }
            }
        }

        branch_2_name = "branch_test"
        _ = await create_branch(branch_name=branch_2_name, db=db)

        with patch("infrahub.git.tasks.lock"):
            client_repository = await client.create(
                kind=InfrahubKind.READONLYREPOSITORY,
                data={"name": "car-dealership", "location": f"{git_repos_source_dir_module_scope}/car-dealership"},
            )
            await client_repository.save()

        repository: CoreReadOnlyRepository = await NodeManager.get_one(
            db=db, id=client_repository.id, kind=InfrahubKind.READONLYREPOSITORY, raise_on_error=True
        )

        assert repository.commit.value
        assert repository.internal_status.value == "active"

        query_convert_repo = """
            mutation($node_id: String!, $target_kind: String!, $fields_mapping: GenericScalar!) {
                ConvertObjectType(data: {
                        node_id: $node_id,
                        target_kind: $target_kind,
                        fields_mapping: $fields_mapping
                    }) {
                        ok
                        node
                }
            }
        """

        # Reconstruct fields mapping to use for the convert object type endpoint
        mapping = {}
        for field_name, field_infos in conversion_response["FieldsMappingTypeConversion"]["mapping"].items():
            if field_infos["source_field_name"] is not None:
                mapping[field_name] = ConversionFieldInput(source_field=field_infos["source_field_name"])
            else:
                assert field_name == "default_branch"

        mapping["default_branch"] = ConversionFieldInput(data=ConversionFieldValue(attribute_value=default_branch.name))
        mapping_dict = {field_name: model.model_dump(mode="json") for field_name, model in mapping.items()}

        with patch("infrahub.git.tasks.lock"):
            conversion_response = await client.execute_graphql(
                query=query_convert_repo,
                variables={
                    "branch": default_branch.name,
                    "node_id": str(repository.id),
                    "fields_mapping": mapping_dict,
                    "target_kind": "CoreRepository",
                },
            )

        assert conversion_response["ConvertObjectType"]["ok"] is True
        res_node = conversion_response["ConvertObjectType"]["node"]
        assert res_node["__kind__"] == "CoreRepository"

        new_repo_id = conversion_response["ConvertObjectType"]["node"]["id"]
        new_repo_main = await NodeManager.get_one(db=db, id=new_repo_id, raise_on_error=True)
        assert repository.commit.value == new_repo_main.commit.value

        await self._validate_read_write_repo_init(branch=default_branch, repository=new_repo_main, service=service)

        await self._validate_repo_groups(db=db, repository=repository)

        await self._validate_branches_status(
            db=db, branch_2_name=branch_2_name, default_branch_name=default_branch.name
        )

        await self._validate_rebase(
            branch_name=branch_2_name,
            client=client,
            db=db,
            new_repo_id=new_repo_id,
            original_commit=repository.commit.value,
        )

        query_delete = await DeleteAfterTimeQuery.init(db=db, timestamp=start_time)
        await query_delete.execute(db=db)

    async def _validate_repo_groups(self, db: InfrahubDatabase, repository: CoreGenericRepository):
        # Make sure old repository groups has been deleted
        for old_repo_group in (await repository.groups_objects.get_peers(db=db)).values():
            res = await NodeManager.get_one(
                db=db,
                id=old_repo_group.id,
                kind=InfrahubKind.REPOSITORYGROUP,
            )
            assert res is None

    async def _validate_read_write_repo_init(
        self, branch: Branch, repository: CoreGenericRepository, service: InfrahubServices
    ):
        # Now make sure repository has been correctly initialized
        repo_intern = InfrahubRepository(  # type: ignore[call-arg]
            id=UUID(repository.id),
            name=repository.name.value,
            location=repository.location.value,
            client=service.client,
            default_branch_name=branch.name,
            infrahub_branch_name=branch.name,
            service=service,
        )
        repo_intern.validate_local_directories()

    async def _validate_branches_status(self, db: InfrahubDatabase, branch_2_name: str, default_branch_name: str):
        # Make sure other branches are in NEED_REBASE state
        br2 = await Branch.get_by_name(name=branch_2_name, db=db)
        assert br2.status == BranchStatus.NEED_REBASE.value

        # Make sure main/global branches are still in OPEN state
        main_branch = await Branch.get_by_name(name=default_branch_name, db=db)
        assert main_branch.status == BranchStatus.OPEN.value
        global_branch = await Branch.get_by_name(name=GLOBAL_BRANCH_NAME, db=db)
        assert global_branch.status == BranchStatus.OPEN.value

    async def _create_proposed_change_and_wait_for_validators(
        self, repository_id: str, client: InfrahubClient, source_branch: str, target_branch: str, db: InfrahubDatabase
    ):
        """
        Create a proposed change and make sure validators are attached to the input repository.
        """

        proposed_change_create = await client.create(
            kind=InfrahubKind.PROPOSEDCHANGE,
            data={"source_branch": source_branch, "destination_branch": target_branch, "name": "test-pc"},
        )
        await proposed_change_create.save()

        # Wait for validators to be created by polling instead of sleeping
        max_wait_time = 10.0  # seconds
        poll_interval = 0.5  # seconds
        elapsed_time = 0.0

        user_validators_created = False
        while elapsed_time < max_wait_time:
            users_validators = await client.all(
                kind=InfrahubKind.USERVALIDATOR,
            )

            if users_validators and any(validator.repository.id == repository_id for validator in users_validators):
                user_validators_created = True
                break

            await asyncio.sleep(poll_interval)
            elapsed_time += poll_interval

        assert user_validators_created, (
            "No user validators were created by the proposed change, `CoreUserValidator.repository` unidirectional relationship would not be tested"
        )
        # Note that ideally repository_validators would be tested as well
