from __future__ import annotations

from typing import TYPE_CHECKING, Any

from infrahub import lock
from infrahub.lock import InfrahubMultiLock
from infrahub.rack_elevation.errors import raise_placement_violation
from infrahub.rack_elevation.locks import rack_lock_name
from infrahub.rack_elevation.mapped.mapping import MountableKindFields, RackMappingIndex
from infrahub.rack_elevation.mapped.provider import MappedRackElevationProvider

from .main import InfrahubMutation

if TYPE_CHECKING:
    from graphene import InputObjectType
    from graphql import GraphQLResolveInfo
    from typing_extensions import Self

    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase
    from infrahub.graphql.initialization import GraphqlContext


class InfrahubMappedRackMountableMutation(InfrahubMutation):
    """Create, update and upsert mutations of a kind with the `mountable` role.

    Every save is checked against the rack the item ends up in, under the lock of each rack involved.
    """

    class Meta:
        abstract = True

    @classmethod
    def _get_index(cls, db: InfrahubDatabase, branch: Branch) -> RackMappingIndex:
        return RackMappingIndex.from_schema_branch(schema_branch=db.schema.get_schema_branch(name=branch.name))

    @classmethod
    def _get_lock_names(
        cls, fields: MountableKindFields, branch: Branch, data: InputObjectType, current_rack_id: str | None
    ) -> list[str]:
        target = data.get(fields.rack_relationship)
        target_rack_id = target.get("id") if isinstance(target, dict) else None
        rack_ids = {rack_id for rack_id in (target_rack_id, current_rack_id) if rack_id}
        return sorted(rack_lock_name(branch.name, rack_id) for rack_id in rack_ids)

    @classmethod
    async def _check_saved_item(cls, db: InfrahubDatabase, branch: Branch, obj: Node) -> None:
        index = cls._get_index(db=db, branch=branch)
        provider = MappedRackElevationProvider(db=db, branch=branch, at=None, index=index)
        violation = await provider.find_violation(item_id=obj.get_id())
        if violation is not None:
            raise_placement_violation(
                violation=violation,
                node_kind=obj.get_kind(),
                field_name=index.mountable_kinds[obj.get_kind()].customer_field_name(argument=violation.field),
            )

    @classmethod
    async def mutate_create(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        database: InfrahubDatabase | None = None,
        override_data: dict[str, Any] | None = None,
    ) -> tuple[Node, Self]:
        graphql_context: GraphqlContext = info.context
        db = database or graphql_context.db
        fields = cls._get_index(db=db, branch=branch).mountable_kinds[cls._meta.active_schema.kind]
        lock_names = cls._get_lock_names(fields=fields, branch=branch, data=data, current_rack_id=None)

        async with InfrahubMultiLock(lock_registry=lock.registry, locks=lock_names):
            if db.is_transaction:
                obj, mutation = await super().mutate_create(
                    info=info, data=data, branch=branch, database=db, override_data=override_data
                )
                await cls._check_saved_item(db=db, branch=branch, obj=obj)
                return obj, mutation
            async with db.start_transaction() as dbt:
                obj, mutation = await super().mutate_create(
                    info=info, data=data, branch=branch, database=dbt, override_data=override_data
                )
                await cls._check_saved_item(db=dbt, branch=branch, obj=obj)
            return obj, mutation

    @classmethod
    async def _call_mutate_update(
        cls,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        db: InfrahubDatabase,
        obj: Node,
        skip_uniqueness_check: bool = False,
    ) -> tuple[Node, Self]:
        fields = cls._get_index(db=db, branch=branch).mountable_kinds[obj.get_kind()]
        current_rack_id = await getattr(obj, fields.rack_relationship).get_peer_id(db=db)
        lock_names = cls._get_lock_names(fields=fields, branch=branch, data=data, current_rack_id=current_rack_id)
        async with InfrahubMultiLock(lock_registry=lock.registry, locks=lock_names):
            return await super()._call_mutate_update(
                info=info, data=data, branch=branch, db=db, obj=obj, skip_uniqueness_check=skip_uniqueness_check
            )

    @classmethod
    async def mutate_update_object(
        cls,
        db: InfrahubDatabase,
        info: GraphQLResolveInfo,
        data: InputObjectType,
        branch: Branch,
        obj: Node,
        skip_uniqueness_check: bool = False,
    ) -> Node:
        obj = await super().mutate_update_object(
            db=db, info=info, data=data, branch=branch, obj=obj, skip_uniqueness_check=skip_uniqueness_check
        )
        await cls._check_saved_item(db=db, branch=branch, obj=obj)
        return obj
