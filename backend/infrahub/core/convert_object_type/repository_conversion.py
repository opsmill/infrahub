from infrahub import lock
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, RepositoryDeliveryStatus
from infrahub.core.convert_object_type.object_conversion import (
    ConversionFieldInput,
    convert_object_type,
    validate_conversion,
)
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.protocols import CoreReadOnlyRepository, CoreRepository, CoreRepositoryValidator, CoreUserValidator
from infrahub.core.schema import NodeSchema
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import DeliveryPendingError, ValidationError
from infrahub.git.writeback.ports import DeliveryStatePort
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
    delivery_state: DeliveryStatePort,
) -> Node:
    """Delete the node and return the new created one. If creation fails, the node is not deleted, and raise an error.

    An extra check is performed on input node peers relationships to make sure they are still valid.

    Raises:
        ValidationError: The mapping sets a read-only attribute of the target kind.
        DeliveryPendingError: The repository has pending pushes or held regeneration, which the deletion of the
            node would drop.

    """
    read_only_inputs = sorted(
        name
        for name, field_input in mapping.items()
        if (field_input.source_field is not None or field_input.data is not None)
        and (attribute := target_schema.get_attribute_or_none(name=name)) is not None
        and attribute.read_only
    )
    if read_only_inputs:
        raise ValidationError(
            input_value=(
                f"A conversion to {target_schema.kind} cannot set the read-only attributes "
                f"{', '.join(read_only_inputs)}."
            )
        )

    repo_name = repository.name.value
    async with lock.registry.get(name=repo_name, namespace="repository"):
        if repository.get_kind() == InfrahubKind.REPOSITORY:
            delivery = await delivery_state.read(repository_id=repository.id)
            if delivery.status != RepositoryDeliveryStatus.NONE:
                raise DeliveryPendingError(repository_name=repo_name)
            if not delivery.held.is_empty:
                raise DeliveryPendingError(repository_name=repo_name, regeneration_held=True)

        async with db.start_transaction() as dbt:
            timestamp_before_conversion = Timestamp()

            # Fetch validators before deleting the repository otherwise validator-repository would no longer exist
            user_validators = await NodeManager.query(
                db=dbt, schema=CoreUserValidator, prefetch_relationships=True, filters={"repository__id": repository.id}
            )
            repository_validators = await NodeManager.query(
                db=dbt,
                schema=CoreRepositoryValidator,
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
        repository_groups = (await repository.groups_objects.get_peers(db=db, peer_type=Node)).values()
        for repository_group in repository_groups:
            await NodeManager.delete(db=db, branch=branch, nodes=[repository_group], cascade_delete=False)

    return new_repository
