"""Organization registry slice: organizations, platforms, tags, ASNs, BGP peer groups.

Faithful transcription of ``models/infrastructure_edge.py``:

* data tables ``PLATFORMS`` (lines 415-444), ``TAGS`` (line 677),
  ``ORGANIZATIONS`` (lines 679-702), ``ASNS`` (lines 704-724) and
  ``BGP_PEER_GROUPS`` (lines 799-835) — including the script's
  ``EXPORT_POP_GLOBLA`` typo,
* ``prepare_platforms`` (line 2463), ``prepare_organizations`` (line 2453),
  ``prepare_asns`` (line 2359), ``prepare_tags`` (line 2474) and
  ``prepare_bgp_peer_groups`` (line 2393),
* with the batch boundaries of ``run()`` (lines 2598-2624): platforms +
  organizations in one batch (the script shares that batch with the standard
  groups and interface profiles owned by the ``data_profiles_groups`` slice),
  then ASNs + tags, then BGP peer groups.

Attribute metadata mirrors the script exactly: ASN name/asn/description use
``source=crm-sync`` and ``owner=cobrian``, the ASN organization relationship
uses ``source=crm-sync``, tags and BGP peer-group attributes use
``source=pop-builder``; organization names are ``is_protected``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from data.handles import OrgRegistryHandle

if TYPE_CHECKING:
    from infrahub_sdk import InfrahubClientSync
    from infrahub_sdk.batch import InfrahubBatchSync
    from infrahub_sdk.node import InfrahubNodeSync

    from data.handles import RbacHandle

BRANCH = "main"

# name / type; kind is f"Organization{type.title()}" (lines 679-702)
ORGANIZATIONS = (
    {"name": "Arelion", "type": "provider"},
    {"name": "Colt Technology Services", "type": "provider"},
    {"name": "Verizon Business", "type": "provider"},
    {"name": "GTT Communications", "type": "provider"},
    {"name": "Hurricane Electric", "type": "provider"},
    {"name": "Lumen", "type": "provider"},
    {"name": "Zayo", "type": "provider"},
    {"name": "Equinix", "type": "provider"},
    {"name": "Interxion", "type": "provider"},
    {"name": "PCCW Global", "type": "provider"},
    {"name": "Orange S.A", "type": "provider"},
    {"name": "Tata Communications", "type": "provider"},
    {"name": "Sprint", "type": "provider"},
    {"name": "NTT America", "type": "provider"},
    {"name": "Cogent Communications", "type": "provider"},
    {"name": "Comcast Cable Communication", "type": "provider"},
    {"name": "Telecom Italia Sparkle", "type": "provider"},
    {"name": "AT&T Services", "type": "provider"},
    {"name": "Duff", "type": "tenant"},
    {"name": "Juniper", "type": "manufacturer"},
    {"name": "Cisco", "type": "manufacturer"},
    {"name": "Arista", "type": "manufacturer"},
)

# name / nornir_platform / napalm_driver / netmiko_device_type / ansible_network_os (lines 415-444)
PLATFORMS = (
    {
        "name": "Cisco IOS",
        "nornir_platform": "ios",
        "napalm_driver": "ios",
        "netmiko_device_type": "cisco_ios",
        "ansible_network_os": "ios",
    },
    {
        "name": "Cisco NXOS SSH",
        "nornir_platform": "nxos_ssh",
        "napalm_driver": "nxos_ssh",
        "netmiko_device_type": "cisco_nxos",
        "ansible_network_os": "nxos",
    },
    {
        "name": "Juniper JunOS",
        "nornir_platform": "junos",
        "napalm_driver": "junos",
        "netmiko_device_type": "juniper_junos",
        "ansible_network_os": "junos",
    },
    {
        "name": "Arista EOS",
        "nornir_platform": "eos",
        "napalm_driver": "eos",
        "netmiko_device_type": "arista_eos",
        "ansible_network_os": "eos",
    },
)

# (line 677)
TAGS = ["blue", "green", "red"]

# asn / organization; name is f"AS{asn}" (lines 704-724)
ASNS = (
    {"asn": 1299, "organization": "Arelion"},
    {"asn": 64496, "organization": "Duff"},
    {"asn": 8220, "organization": "Colt Technology Services"},
    {"asn": 701, "organization": "Verizon Business"},
    {"asn": 3257, "organization": "GTT Communications"},
    {"asn": 6939, "organization": "Hurricane Electric"},
    {"asn": 3356, "organization": "Lumen"},
    {"asn": 6461, "organization": "Zayo"},
    {"asn": 24115, "organization": "Equinix"},
    {"asn": 20710, "organization": "Interxion"},
    {"asn": 3491, "organization": "PCCW Global"},
    {"asn": 5511, "organization": "Orange S.A"},
    {"asn": 6453, "organization": "Tata Communications"},
    {"asn": 1239, "organization": "Sprint"},
    {"asn": 2914, "organization": "NTT America"},
    {"asn": 174, "organization": "Cogent Communications"},
    {"asn": 7922, "organization": "Comcast Cable Communication"},
    {"asn": 6762, "organization": "Telecom Italia Sparkle"},
    {"asn": 7018, "organization": "AT&T Services"},
)

# name / import_policies / export_policies / local_as / remote_as (lines 799-835)
# NB: "EXPORT_POP_GLOBLA" is the script's typo — preserved for parity.
BGP_PEER_GROUPS = (
    {
        "name": "POP_INTERNAL",
        "import_policies": "IMPORT_INTRA_POP",
        "export_policies": "EXPORT_INTRA_POP",
        "local_as": "Duff",
        "remote_as": "Duff",
    },
    {
        "name": "POP_GLOBAL",
        "import_policies": "IMPORT_POP_GLOBAL",
        "export_policies": "EXPORT_POP_GLOBLA",
        "local_as": "Duff",
        "remote_as": None,
    },
    {
        "name": "UPSTREAM_DEFAULT",
        "import_policies": "IMPORT_UPSTREAM",
        "export_policies": "EXPORT_PUBLIC_PREFIX",
        "local_as": "Duff",
        "remote_as": None,
    },
    {
        "name": "UPSTREAM_ARELION",
        "import_policies": "IMPORT_UPSTREAM",
        "export_policies": "EXPORT_PUBLIC_PREFIX",
        "local_as": "Duff",
        "remote_as": "Arelion",
    },
    {
        "name": "IX_DEFAULT",
        "import_policies": "IMPORT_IX",
        "export_policies": "EXPORT_PUBLIC_PREFIX",
        "local_as": "Duff",
        "remote_as": None,
    },
)


def _prepare_platforms(client: InfrahubClientSync, batch: InfrahubBatchSync) -> dict[str, InfrahubNodeSync]:
    """Transcribes ``prepare_platforms`` (lines 2463-2471)."""
    platforms: dict[str, InfrahubNodeSync] = {}
    for platform in PLATFORMS:
        obj = client.create(branch=BRANCH, kind="InfraPlatform", data=dict(platform))
        batch.add(task=obj.save, node=obj)
        platforms[platform["name"]] = obj
    return platforms


def _prepare_organizations(client: InfrahubClientSync, batch: InfrahubBatchSync) -> dict[str, InfrahubNodeSync]:
    """Transcribes ``prepare_organizations`` (lines 2453-2460)."""
    organizations: dict[str, InfrahubNodeSync] = {}
    for org in ORGANIZATIONS:
        data_org = {
            "name": {"value": org["name"], "is_protected": True},
        }
        obj = client.create(branch=BRANCH, kind=f"Organization{org['type'].title()}", data=data_org)
        batch.add(task=obj.save, node=obj)
        organizations[org["name"]] = obj
    return organizations


def _prepare_asns(
    client: InfrahubClientSync,
    batch: InfrahubBatchSync,
    organizations: dict[str, InfrahubNodeSync],
    crm_sync_id: str,
    cobrian_id: str,
) -> dict[str, InfrahubNodeSync]:
    """Transcribes ``prepare_asns`` (lines 2359-2390); ASNs are keyed by organization name."""
    organizations_dict = {org["name"]: org["type"] for org in ORGANIZATIONS}
    asns: dict[str, InfrahubNodeSync] = {}
    for asn in ASNS:
        organization_type = organizations_dict.get(asn["organization"])
        asn_name = f"AS{asn['asn']}"
        data_asn: dict[str, Any] = {
            "name": {"value": asn_name, "source": crm_sync_id, "owner": cobrian_id},
            "asn": {"value": asn["asn"], "source": crm_sync_id, "owner": cobrian_id},
        }
        if organization_type:
            data_asn["description"] = {
                "value": f"{asn_name} for {asn['organization']}",
                "source": crm_sync_id,
                "owner": cobrian_id,
            }
            data_asn["organization"] = {
                "id": organizations[asn["organization"]].id,
                "source": crm_sync_id,
            }
        else:
            data_asn["description"] = {"value": asn_name, "source": crm_sync_id, "owner": cobrian_id}
        obj = client.create(branch=BRANCH, kind="InfraAutonomousSystem", data=data_asn)
        batch.add(task=obj.save, node=obj)
        asns[asn["organization"]] = obj
    return asns


def _prepare_tags(
    client: InfrahubClientSync, batch: InfrahubBatchSync, pop_builder_id: str
) -> dict[str, InfrahubNodeSync]:
    """Transcribes ``prepare_tags`` (lines 2474-2484)."""
    tags: dict[str, InfrahubNodeSync] = {}
    for tag in TAGS:
        obj = client.create(branch=BRANCH, kind="BuiltinTag", name={"value": tag, "source": pop_builder_id})
        batch.add(task=obj.save, node=obj)
        tags[tag] = obj
    return tags


def _prepare_bgp_peer_groups(
    client: InfrahubClientSync,
    batch: InfrahubBatchSync,
    asns: dict[str, InfrahubNodeSync],
    pop_builder_id: str,
) -> dict[str, InfrahubNodeSync]:
    """Transcribes ``prepare_bgp_peer_groups`` (lines 2393-2426)."""
    peer_groups: dict[str, InfrahubNodeSync] = {}
    for peer_group in BGP_PEER_GROUPS:
        remote_as_id = None
        local_as_id = None
        local_as = asns.get(peer_group["local_as"])
        remote_as = asns.get(peer_group["remote_as"]) if peer_group["remote_as"] else None
        if remote_as:
            remote_as_id = remote_as.id
        if local_as:
            local_as_id = local_as.id

        obj = client.create(
            branch=BRANCH,
            kind="InfraBGPPeerGroup",
            name={"value": peer_group["name"], "source": pop_builder_id},
            import_policies={"value": peer_group["import_policies"], "source": pop_builder_id},
            export_policies={"value": peer_group["export_policies"], "source": pop_builder_id},
            local_as={"id": local_as_id},
            remote_as={"id": remote_as_id},
        )
        batch.add(task=obj.save, node=obj)
        peer_groups[peer_group["name"]] = obj
    return peer_groups


@pytest.fixture(scope="session")
def data_org_registry(
    data_client: InfrahubClientSync,
    schema_base: None,
    data_rbac: RbacHandle,
    infrahub_provisioned_externally: bool,
) -> OrgRegistryHandle:
    """Organizations, platforms, tags, ASNs and BGP peer groups of the demo dataset."""
    if infrahub_provisioned_externally:
        return OrgRegistryHandle.external()

    batch = data_client.create_batch()
    platforms = _prepare_platforms(client=data_client, batch=batch)
    organizations = _prepare_organizations(client=data_client, batch=batch)
    for _ in batch.execute():
        pass

    batch = data_client.create_batch()
    asns = _prepare_asns(
        client=data_client,
        batch=batch,
        organizations=organizations,
        crm_sync_id=data_rbac.accounts["crm-sync"],
        cobrian_id=data_rbac.accounts["cobrian"],
    )
    tags = _prepare_tags(client=data_client, batch=batch, pop_builder_id=data_rbac.accounts["pop-builder"])
    for _ in batch.execute():
        pass

    batch = data_client.create_batch()
    peer_groups = _prepare_bgp_peer_groups(
        client=data_client,
        batch=batch,
        asns=asns,
        pop_builder_id=data_rbac.accounts["pop-builder"],
    )
    for _ in batch.execute():
        pass

    return OrgRegistryHandle(
        organizations={key: node.id for key, node in organizations.items()},
        platforms={key: node.id for key, node in platforms.items()},
        tags={key: node.id for key, node in tags.items()},
        asns={key: node.id for key, node in asns.items()},
        peer_groups={key: node.id for key, node in peer_groups.items()},
    )
