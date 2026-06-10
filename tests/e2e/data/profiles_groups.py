"""Profiles & groups slice: interface profiles and standard groups.

Faithful transcription of ``models/infrastructure_edge.py``:

* data tables ``GROUPS`` (lines 785-797) and ``INTERFACE_PROFILES``
  (lines 837-840),
* ``prepare_groups`` (line 2429) and ``prepare_interface_profiles``
  (line 2437),
* batch boundary from ``run()`` (lines 2598-2607): groups and interface
  profiles share one batch (the script also packs the platforms and
  organizations owned by the ``data_org_registry`` slice into it).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from data.handles import ProfilesGroupsHandle

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClientSync

BRANCH = "main"

# name / label (models/infrastructure_edge.py lines 785-797).
# leaf_switch and juniper_devices are commented out in the script and deliberately absent here.
GROUPS = (
    {"name": "edge_router", "label": "Edge Router"},
    {"name": "core_router", "label": "Core Router"},
    {"name": "cisco_devices", "label": "Cisco Devices"},
    {"name": "arista_devices", "label": "Arista Devices"},
    {"name": "upstream_interfaces", "label": "Upstream Interfaces"},
    {"name": "backbone_interfaces", "label": "Backbone Interfaces"},
    {"name": "maintenance_circuits", "label": "Circuits in Maintenance"},
    {"name": "provisioning_circuits", "label": "Circuits in Provisioning"},
    {"name": "backbone_services", "label": "Backbone Services"},
)

# name / mtu / kind; profile kind is f"Profile{kind}" (lines 837-840)
INTERFACE_PROFILES = (
    {"name": "upstream_profile", "mtu": 1515, "kind": "InfraInterfaceL3"},
    {"name": "backbone_profile", "mtu": 9216, "kind": "InfraInterfaceL3"},
)


@pytest.fixture(scope="session")
def data_profiles_groups(
    data_client: InfrahubClientSync,
    schema_base: None,
    infrahub_provisioned_externally: bool,
) -> ProfilesGroupsHandle:
    """Standard groups and interface profiles of the demo dataset."""
    if infrahub_provisioned_externally:
        return ProfilesGroupsHandle.external()

    batch = data_client.create_batch()

    standard_groups = {}
    for group in GROUPS:
        obj = data_client.create(branch=BRANCH, kind="CoreStandardGroup", data=dict(group))
        batch.add(task=obj.save, node=obj)
        standard_groups[group["name"]] = obj

    interface_profiles = {}
    for intf_profile in INTERFACE_PROFILES:
        data_profile = {
            "profile_name": {"value": intf_profile["name"]},
            "mtu": {"value": intf_profile["mtu"]},
        }
        profile = data_client.create(branch=BRANCH, kind=f"Profile{intf_profile['kind']}", data=data_profile)
        batch.add(task=profile.save, node=profile)
        interface_profiles[intf_profile["name"]] = profile

    for _ in batch.execute():
        pass

    return ProfilesGroupsHandle(
        interface_profiles={key: node.id for key, node in interface_profiles.items()},
        standard_groups={key: node.id for key, node in standard_groups.items()},
    )
