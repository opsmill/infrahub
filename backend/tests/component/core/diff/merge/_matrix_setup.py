"""Shared orchestration: stage every change type on the diff branch.

Used by matrix tests so each test differs only in how scenario-specific
setup (conflicts, migrations) is layered on top. The branch-side staging here
is identical across tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._contexts import MatrixContexts
from ._setup import (
    setup_added_node,
    setup_added_one_relationship,
    setup_cleared_attribute_property,
    setup_cleared_attribute_value,
    setup_cleared_one_relationship,
    setup_cleared_relationship_property,
    setup_deleted_node,
    setup_updated_attribute_property,
    setup_updated_attribute_value,
    setup_updated_relationship_property,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.node import Node
    from infrahub.database import InfrahubDatabase


async def stage_all_change_types(
    *,
    db: InfrahubDatabase,
    branch: Branch,
    person_john: Node,
    person_jane: Node,
    person_alfred: Node,
    car_accord: Node,
    car_camry: Node,
    car_yaris: Node,
    car_prop_cleared: Node,
    car_driver: Node,
    manufacturer_toyota: Node,
    car_no_manufacturer: Node,
    car_with_manufacturer: Node,
    car_tagged: Node,
    added_node_kind: str = "TestCar",
) -> MatrixContexts:
    """Stage every change type on ``branch`` and return the collected contexts."""
    contexts = MatrixContexts()

    contexts.added_node = await setup_added_node(
        db=db,
        branch=branch,
        kind=added_node_kind,
        attribute_values={"name": "new-car", "nbr_seats": 4, "is_electric": True},
        one_relationship_peers={"owner": person_alfred.id},
        branch_user="branch-added-node-user",
    )

    contexts.deleted_node = await setup_deleted_node(
        db=db,
        branch=branch,
        node_to_delete=car_camry,
        branch_user="branch-deleted-node-user",
        peer_node_ids=[person_jane.id],
    )

    contexts.updated_attribute_values.append(
        await setup_updated_attribute_value(
            db=db,
            branch=branch,
            node_on_main=car_accord,
            attribute_name="color",
            new_value="#FF0000",
            branch_user="branch-attr-value-user",
        )
    )

    # List-typed attribute update: overwrite an existing list value on main.
    contexts.updated_attribute_values.append(
        await setup_updated_attribute_value(
            db=db,
            branch=branch,
            node_on_main=car_tagged,
            attribute_name="tags",
            new_value=["gamma", "delta", "epsilon"],
            branch_user="branch-attr-list-user",
        )
    )

    contexts.cleared_attribute_value = await setup_cleared_attribute_value(
        db=db,
        branch=branch,
        node_on_main=car_yaris,
        attribute_name="nbr_seats",
        branch_user="branch-attr-clear-user",
    )

    contexts.added_relationships.append(
        await setup_added_one_relationship(
            db=db,
            branch=branch,
            node_on_main=car_accord,
            relationship_name="driver",
            new_peer_id=person_jane.id,
            branch_user="branch-rel-add-user",
        )
    )

    contexts.deleted_relationships.append(
        await setup_cleared_one_relationship(
            db=db,
            branch=branch,
            node_on_main=car_driver,
            relationship_name="driver",
            existing_peer_id=person_jane.id,
            branch_user="branch-rel-clear-user",
        )
    )

    contexts.updated_attribute_properties.append(
        await setup_updated_attribute_property(
            db=db,
            branch=branch,
            node_on_main=car_accord,
            attribute_name="name",
            property_name="source",
            peer_node=person_alfred,
            branch_user="branch-attr-source-user",
        )
    )

    contexts.updated_attribute_properties.append(
        await setup_updated_attribute_property(
            db=db,
            branch=branch,
            node_on_main=car_yaris,
            attribute_name="color",
            property_name="is_protected",
            bool_value=True,
            branch_user="branch-attr-protect-user",
        )
    )

    contexts.cleared_attribute_properties.append(
        await setup_cleared_attribute_property(
            db=db,
            branch=branch,
            node_on_main=car_prop_cleared,
            attribute_name="name",
            property_name="source",
            branch_user="branch-attr-source-clear-user",
        )
    )

    contexts.updated_relationship_properties.append(
        await setup_updated_relationship_property(
            db=db,
            branch=branch,
            node_on_main=car_yaris,
            relationship_name="owner",
            peer_id=person_jane.id,
            property_name="source",
            property_peer_node=person_alfred,
            branch_user="branch-rel-source-user",
        )
    )

    contexts.cleared_relationship_properties.append(
        await setup_cleared_relationship_property(
            db=db,
            branch=branch,
            node_on_main=car_prop_cleared,
            relationship_name="owner",
            peer_id=person_john.id,
            property_name="source",
            branch_user="branch-rel-source-clear-user",
        )
    )

    # Aware -> agnostic relationship add: branch sets TestCar.manufacturer to an
    # existing TestManufacturer (branch: AGNOSTIC) peer.
    contexts.added_relationships.append(
        await setup_added_one_relationship(
            db=db,
            branch=branch,
            node_on_main=car_no_manufacturer,
            relationship_name="manufacturer",
            new_peer_id=manufacturer_toyota.id,
            branch_user="branch-rel-add-agnostic-user",
        )
    )

    # Aware -> agnostic relationship clear: branch clears a pre-existing
    # TestCar.manufacturer pointing at a TestManufacturer (AGNOSTIC) peer.
    contexts.deleted_relationships.append(
        await setup_cleared_one_relationship(
            db=db,
            branch=branch,
            node_on_main=car_with_manufacturer,
            relationship_name="manufacturer",
            existing_peer_id=manufacturer_toyota.id,
            branch_user="branch-rel-clear-agnostic-user",
        )
    )

    return contexts
