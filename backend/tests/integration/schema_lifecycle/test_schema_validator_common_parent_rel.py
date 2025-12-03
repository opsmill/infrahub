import copy
from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk import InfrahubClient
from infrahub_sdk.exceptions import GraphQLError

from infrahub.core.manager import NodeManager
from infrahub.core.schema import SchemaRoot
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_no_duplicate_relationships, verify_no_edges_added_after_node_delete
from tests.constants import TestKind
from tests.helpers.schema import DEVICE_SCHEMA
from tests.helpers.schema.device import DATACENTER_DEVICE, LAG_INTERFACE
from tests.helpers.schema.location import (
    DATACENTER_HIERARCHY,
    DATACENTER_RACK,
    DATACENTER_RACK_WITH_CONSTRAINT,
    DATACENTER_SITE,
)

from .shared import TestSchemaLifecycleBase

if TYPE_CHECKING:
    from infrahub_sdk.node import InfrahubNode


class TestSchemaLifecyclePeerParentUpdate(TestSchemaLifecycleBase):
    branch_name = "parent-test-branch"

    @pytest.fixture(scope="class")
    def schema_network(self) -> dict[str, Any]:
        DEVICE_SCHEMA.version = "1.0"
        return DEVICE_SCHEMA.model_dump()

    @pytest.fixture(scope="class")
    def schema_lag_interface(self) -> dict[str, Any]:
        lag_without_constraint = copy.deepcopy(LAG_INTERFACE)
        lag_without_constraint.relationships[0].common_parent = None
        return SchemaRoot(version="1.0", generics=[], nodes=[lag_without_constraint]).model_dump()

    @pytest.fixture(scope="class")
    def schema_constrained_lag_interface(self) -> dict[str, Any]:
        return SchemaRoot(version="1.0", generics=[], nodes=[LAG_INTERFACE]).model_dump()

    async def test_step_01_create_branch(self, client: InfrahubClient) -> None:
        branch = await client.branch.create(branch_name=self.branch_name, sync_with_git=False)
        assert branch

    async def test_step_02_load_schema(self, client: InfrahubClient, schema_network: dict[str, Any]) -> None:
        response = await client.schema.load(schemas=[schema_network], branch=self.branch_name)
        assert not response.errors

    async def test_step_03_add_lag_node_to_schema(
        self, db: InfrahubDatabase, client: InfrahubClient, schema_lag_interface: dict[str, Any]
    ) -> None:
        response = await client.schema.load(schemas=[schema_lag_interface], branch=self.branch_name)
        assert not response.errors

    async def test_step_04_create_devices_and_lags(self, db: InfrahubDatabase, client: InfrahubClient) -> None:
        for name in ["device_1", "device_2"]:
            device = await client.create(
                branch=self.branch_name,
                kind=TestKind.DEVICE,
                name=name,
                manufacturer="Foo",
                weight=10,
                airflow="Front to rear",
            )
            await device.save()

            interfaces: list[InfrahubNode] = []
            for if_name in ["et-0/0/0", "et-0/0/1", "et-0/0/2", "et-0/0/3"]:
                interface = await client.create(
                    branch=self.branch_name,
                    kind=TestKind.PHYSICAL_INTERFACE,
                    name=if_name,
                    phys_type="QSFP28 (100GE)",
                    device=device,
                )
                await interface.save()
                interfaces.append(interface)

            lag = await client.create(
                branch=self.branch_name,
                kind=TestKind.LAG_INTERFACE,
                name="ae0",
                device=device,
                members=[i.id for i in interfaces],
            )
            await lag.save()

            last_interface = await NodeManager.get_one(db=db, branch=self.branch_name, id=interfaces[-1].id)
            await last_interface.delete(db=db)

    async def test_step05_set_constraint_to_lag(
        self, db: InfrahubDatabase, client: InfrahubClient, schema_constrained_lag_interface: dict[str, Any]
    ) -> None:
        devices = await NodeManager.query(db=db, branch=self.branch_name, schema=TestKind.DEVICE)
        interfaces = await NodeManager.query(db=db, branch=self.branch_name, schema=TestKind.PHYSICAL_INTERFACE)
        interface_to_invalidate = interfaces[0]
        original_device = await interface_to_invalidate.device.get_peer(db=db)
        other_device = [d for d in devices if d.id != original_device.id][0]
        await interface_to_invalidate.device.update(db=db, data=other_device)
        await interface_to_invalidate.save(db=db)

        response = await client.schema.load(schemas=[schema_constrained_lag_interface], branch=self.branch_name)
        assert response.errors
        error_str = response.errors["errors"][0]["message"]
        assert (
            "Relationship-level 'common_parent' constraint violation on schema 'TestingPhysicalInterface'." in error_str
        )
        assert f"Node (TestingPhysicalInterface(ID: {interface_to_invalidate.id})) is not compliant." in error_str
        assert f"The error relates to field device.id={other_device.id}." in error_str

        interface_to_validate = await NodeManager.get_one(db=db, branch=self.branch_name, id=interface_to_invalidate.id)
        await interface_to_validate.device.update(db=db, data=original_device)
        await interface_to_validate.save(db=db)

        response = await client.schema.load(schemas=[schema_constrained_lag_interface], branch=self.branch_name)
        assert not response.errors

    async def test_step06_create_lag_with_relationship_add(self, db: InfrahubDatabase, client: InfrahubClient) -> None:
        device = await client.get(branch=self.branch_name, kind=TestKind.DEVICE, name__value="device_2")
        interfaces = await NodeManager.query(
            db=db, branch=self.branch_name, schema=TestKind.PHYSICAL_INTERFACE, filters={"device__id": device.id}
        )
        await device.interfaces.fetch()
        lag = await client.create(
            branch=self.branch_name,
            kind=TestKind.LAG_INTERFACE,
            name="ae1",
            device=device,
            members=[interfaces[0].id],
        )
        await lag.save()

        query = """
        mutation {
            RelationshipAdd(
                data: {
                    id: "%s",
                    name: "members",
                    nodes: [ %s ]
                }
            ) {
                ok
            }
        }
        """ % (lag.id, ", ".join(f'{{id: "{i.id}"}}' for i in interfaces[1:]))

        response = await client.execute_graphql(query=query, branch_name=self.branch_name, tracker="add-members-to-lag")
        assert response["RelationshipAdd"]["ok"]

        nodes = []
        for i in lag.members.peer_ids:
            nodes.append(await client.get(branch=self.branch_name, kind=TestKind.PHYSICAL_INTERFACE, id=i))

        assert {n.device.id for n in nodes} == {device.id}

    async def test_step07_incorrectly_update_lag(self, client: InfrahubClient) -> None:
        device1 = await client.get(branch=self.branch_name, kind=TestKind.DEVICE, name__value="device_1")
        device2 = await client.get(branch=self.branch_name, kind=TestKind.DEVICE, name__value="device_2")
        await device2.interfaces.fetch()

        # Get LAG from device 1 and try to add interfaces from device 2 (this must fail)
        lag = await client.get(
            branch=self.branch_name, kind=TestKind.LAG_INTERFACE, name__value="ae0", device__ids=[device1.id]
        )

        query = """
        mutation {
            RelationshipAdd(
                data: {
                    id: "%s",
                    name: "members",
                    nodes: [ %s ]
                }
            ) {
                ok
            }
        }
        """ % (
            lag.id,
            ", ".join(
                f'{{id: "{i.id}"}}'
                for i in device2.interfaces.peers
                if i.get().get_kind() == TestKind.PHYSICAL_INTERFACE
            ),
        )

        with pytest.raises(GraphQLError) as exc:
            await client.execute_graphql(query=query, branch_name=self.branch_name, tracker="add-members-to-lag")

        assert "do not have the same parent" in exc.value.errors[0]["message"]

        await lag.members.fetch()
        nodes = []
        for i in lag.members.peer_ids:
            nodes.append(await client.get(branch=self.branch_name, kind=TestKind.PHYSICAL_INTERFACE, id=i))

        assert {n.device.id for n in nodes} == {device1.id}

    async def test_final_validate(self, db: InfrahubDatabase) -> None:
        await verify_no_duplicate_relationships(db=db)
        await verify_no_edges_added_after_node_delete(db=db)


class TestSchemaLifecycleHierarchyParentUpdate(TestSchemaLifecycleBase):
    """Test common_parent constraint with hierarchical relationships (RelationshipKind.HIERARCHY)."""

    branch_name = "hierarchy-test-branch"

    @pytest.fixture(scope="class")
    def schema_datacenter_base(self) -> dict[str, Any]:
        """Schema with DatacenterSite, DatacenterRack, DatacenterDevice without constraint."""
        return SchemaRoot(
            version="1.0", generics=[DATACENTER_HIERARCHY], nodes=[DATACENTER_SITE, DATACENTER_RACK, DATACENTER_DEVICE]
        ).model_dump()

    @pytest.fixture(scope="class")
    def schema_rack_without_constraint(self) -> dict[str, Any]:
        """Schema for DatacenterRack without common_parent constraint."""
        rack_without_constraint = copy.deepcopy(DATACENTER_RACK)
        return SchemaRoot(version="1.0", generics=[], nodes=[rack_without_constraint]).model_dump()

    @pytest.fixture(scope="class")
    def schema_rack_with_constraint(self) -> dict[str, Any]:
        """Schema for DatacenterRack with common_parent='parent' constraint on devices relationship."""
        return SchemaRoot(version="1.0", generics=[], nodes=[DATACENTER_RACK_WITH_CONSTRAINT]).model_dump()

    async def test_step_01_create_branch(self, client: InfrahubClient) -> None:
        branch = await client.branch.create(branch_name=self.branch_name, sync_with_git=False)
        assert branch

    async def test_step_02_load_base_schema(
        self, client: InfrahubClient, schema_datacenter_base: dict[str, Any]
    ) -> None:
        response = await client.schema.load(schemas=[schema_datacenter_base], branch=self.branch_name)
        assert not response.errors

    async def test_step_03_create_sites_racks_devices(self, db: InfrahubDatabase, client: InfrahubClient) -> None:
        """Create 2 sites, each with 2 racks and 4 devices."""
        for site_num in [1, 2]:
            site = await client.create(
                branch=self.branch_name,
                kind=TestKind.DATACENTER_SITE,
                name=f"site_{site_num}",
                location=f"Location {site_num}",
            )
            await site.save()

            # Create racks for this site
            racks: list[InfrahubNode] = []
            for rack_num in [1, 2]:
                rack = await client.create(
                    branch=self.branch_name,
                    kind=TestKind.DATACENTER_RACK,
                    name=f"rack_{site_num}_{rack_num}",
                    position=rack_num,
                    parent=site,
                )
                await rack.save()
                racks.append(rack)

            # Create devices for this site
            devices: list[InfrahubNode] = []
            for dev_num in [1, 2, 3, 4]:
                device = await client.create(
                    branch=self.branch_name,
                    kind=TestKind.DATACENTER_DEVICE,
                    name=f"device_{site_num}_{dev_num}",
                    device_type="Server",
                    rack=racks[dev_num % 2],
                    parent=site,
                )
                await device.save()
                devices.append(device)

            # Delete last device to test deletion handling
            last_device = await NodeManager.get_one(db=db, branch=self.branch_name, id=devices[-1].id)
            await last_device.delete(db=db)

    async def test_step_04_add_device_to_invalid_rack(self, db: InfrahubDatabase, client: InfrahubClient):
        site_1 = await client.get(branch=self.branch_name, kind=TestKind.DATACENTER_SITE, name__value="site_1")
        # rack_2_2 belongs to site_2, query by name only (site is a hierarchical parent, not a peer relationship)
        rack_2_2 = await client.get(branch=self.branch_name, kind=TestKind.DATACENTER_RACK, name__value="rack_2_2")

        device = await client.create(
            branch=self.branch_name,
            kind=TestKind.DATACENTER_DEVICE,
            name="device_1_4",
            device_type="Server",
            rack=rack_2_2,
            parent=site_1,
        )
        await device.save()
        await device.delete()

    async def test_step_05_set_constraint_to_rack(
        self, db: InfrahubDatabase, client: InfrahubClient, schema_rack_with_constraint: dict[str, Any]
    ) -> None:
        "Load new Rack schema, with common parent constraint, should succeed since there is no violations"
        response = await client.schema.load(schemas=[schema_rack_with_constraint], branch=self.branch_name)
        assert not response.errors

    async def test_step_06_incorrectly_add_device_from_different_site(
        self, db: InfrahubDatabase, client: InfrahubClient
    ) -> None:
        """Attempt to add device from site2 to rack in site1 - should fail."""
        device_2_1 = await client.get(
            branch=self.branch_name, kind=TestKind.DATACENTER_DEVICE, name__value="device_2_1", include=["rack"]
        )
        rack_1_1 = await client.get(branch=self.branch_name, kind=TestKind.DATACENTER_RACK, name__value="rack_1_1")

        device_2_1.rack = None
        await device_2_1.save()

        query = """
        mutation {
            RelationshipAdd(
                data: {
                    id: "%s",
                    name: "devices",
                    nodes: [ {id: "%s"} ]
                }
            ) {
                ok
            }
        }
        """ % (rack_1_1.id, device_2_1.id)

        with pytest.raises(GraphQLError) as exc:
            await client.execute_graphql(query=query, branch_name=self.branch_name, tracker="add-devices-to-rack")

        assert "do not have the same parent" in exc.value.errors[0]["message"]

    async def test_final_validate(self, db: InfrahubDatabase):
        await verify_no_duplicate_relationships(db=db)
        await verify_no_edges_added_after_node_delete(db=db)
