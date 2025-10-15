from infrahub import lock
from infrahub.core.branch import Branch
from infrahub.core.constants.infrahubkind import REPOSITORYVALIDATOR, USERVALIDATOR
from infrahub.core.convert_object_type.object_conversion import (
    ConversionFieldInput,
    convert_object_type,
    validate_conversion,
)
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreReadOnlyRepository, CoreRepository
from infrahub.core.schema import NodeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.message_bus.messages import RefreshRegistryBranches
from infrahub.repositories.create_repository import RepositoryFinalizer
from infrahub.workers.dependencies import get_message_bus


async def convert_repository_type(
    repository: CoreRepository | CoreReadOnlyRepository,
    target_schema: NodeSchema,
    mapping: dict[str, ConversionFieldInput],
    branch: Branch,
    db: InfrahubDatabase,
    repository_post_creator: RepositoryFinalizer,
) -> Node:
    """Delete the node and return the new created one. If creation fails, the node is not deleted, and raise an error.
    An extra check is performed on input node peers relationships to make sure they are still valid."""

    repo_name = repository.name.value
    async with lock.registry.get(name=repo_name, namespace="repository"):
        async with db.start_transaction() as dbt:
            timestamp_before_conversion = Timestamp()

            # Fetch validators before deleting the repository otherwise validator-repository would no longer exist
            user_validators = await NodeManager.query(
                db=dbt, schema=USERVALIDATOR, prefetch_relationships=True, filters={"repository__id": repository.id}
            )
            repository_validators = await NodeManager.query(
                db=dbt,
                schema=REPOSITORYVALIDATOR,
                prefetch_relationships=True,
                filters={"repository__id": repository.id},
            )
            new_repository = await convert_object_type(
                node=repository,  # type: ignore[arg-type]
                target_schema=target_schema,
                mapping=mapping,
                branch=branch,
                db=dbt,
            )

            for user_validator in user_validators:
                await user_validator.repository.update(db=dbt, data=new_repository)
                await user_validator.repository.save(db=dbt)

            for repository_validator in repository_validators:
                await repository_validator.repository.update(db=dbt, data=new_repository)
                await repository_validator.repository.save(db=dbt)

            await validate_conversion(
                deleted_node=repository,  # type: ignore[arg-type]
                branch=branch,
                db=dbt,
                timestamp_before_conversion=timestamp_before_conversion,
            )

        # Refresh outside the transaction otherwise other workers would pull outdated branch objects.
        message_bus = await get_message_bus()
        await message_bus.send(RefreshRegistryBranches())

        # Following call involve a potential update of `commit` value of the newly created repository
        # that would be done from another database connection so it can't be performed within above transaction.
        # Also note since the conversion can only be performed on main branch here, it is fine that we do it
        # after having updating other branches status to NEEDS_REBASE.
        await repository_post_creator.post_create(
            branch=branch,
            obj=new_repository,  # type: ignore
            db=db,
            delete_on_connectivity_failure=False,
        )

        # Delete the RepositoryGroup associated with the old repository, as a new one was created for the new repository.
        repository_groups = (await repository.groups_objects.get_peers(db=db)).values()
        for repository_group in repository_groups:
            await NodeManager.delete(db=db, branch=branch, nodes=[repository_group], cascade_delete=False)

    return new_repository
