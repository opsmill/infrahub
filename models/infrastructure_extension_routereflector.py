import logging
from typing import List

from infrahub_client import InfrahubClient, NodeStore

# flake8: noqa
# pylint: skip-file

ROUTE_REFLECTORS = (
    ("rr1", "active", "type1", "role1", ["red", "green"], "ord1", "192.168.1.1"),
    ("rr1", "active", "type2", "role2", ["red", "blue", "green"], "sfo1", "192.168.1.2"),
)

SITES = ["atl", "ord", "jfk", "den", "dfw", "iad", "bkk", "sfo", "iah", "mco"]

STATUSES = ["active", "provisionning", "maintenance", "drained"]

TAGS = ["blue", "green", "red"]

RR_ROLES = ["role1", "role2"]

ACCOUNTS = (
    ("pop-builder", "Script", "Password123", "read-write"),
    ("CRM Synchronization", "Script", "Password123", "read-write"),
    ("Jack Bauer", "User", "Password123", "read-only"),
    ("Chloe O'Brian", "User", "Password123", "read-write"),
    ("David Palmer", "User", "Password123", "read-write"),
    ("Operation Team", "User", "Password123", "read-only"),
    ("Engineering Team", "User", "Password123", "read-write"),
    ("Architecture Team", "User", "Password123", "read-only"),
)


def site_names_generator(nbr_site=2) -> List[str]:
    """Generate a list of site names by iterating over the list of SITES defined above and by increasing the id.

    site_names_generator(nbr_site=5)
        result >> ["atl1", "ord1", "jfk1", "den1", "dfw1"]

    site_names_generator(nbr_site=12)
        result >> ["atl1", "ord1", "jfk1", "den1", "dfw1", "iad1", "bkk1", "sfo1", "iah1", "mco1", "atl2", "ord2"]
    """

    site_names: List[str] = []

    # Calculate how many loop over the entire list we need to make
    # and how many site we need to generate on the last loop
    nbr_loop = (int(nbr_site / len(SITES))) + 1
    nbr_last_loop = nbr_site % len(SITES) or len(SITES)

    for idx in range(1, 1 + nbr_loop):
        nbr_this_loop = len(SITES)
        if idx == nbr_loop:
            nbr_this_loop = nbr_last_loop

        site_names.extend([f"{site}{idx}" for site in SITES[:nbr_this_loop]])

    return site_names


store = NodeStore()


async def generate_site(client: InfrahubClient, log: logging.Logger, branch: str, site_name: str):
    account_pop = store.get("pop-builder")
    account_crm = store.get("CRM Synchronization")
    active_status = store.get(kind="BuiltinStatus", key="active")

    # --------------------------------------------------
    # Create the Site
    # --------------------------------------------------
    site = await client.create(
        branch=branch,
        kind="BuiltinLocation",
        name={"value": site_name, "is_protected": True, "source": account_crm.id},
        type={"value": "SITE", "is_protected": True, "source": account_crm.id},
    )
    await site.save()
    log.info(f"Created Site: {site_name}")

    return site_name


# ---------------------------------------------------------------
# Use the `infrahubctl run` command line to execute this script
#
#   infrahubctl run models/infrastructure_edge.py
#
# ---------------------------------------------------------------
async def run(client: InfrahubClient, log: logging.Logger, branch: str):
    SITE_NAMES = site_names_generator(nbr_site=5)

    # ------------------------------------------
    # Create User Accounts
    # ------------------------------------------
    batch = await client.create_batch()

    for account in ACCOUNTS:
        obj = await client.create(
            branch=branch,
            kind="CoreAccount",
            data={"name": account[0], "password": account[2], "type": account[1], "role": account[3]},
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=account[0], node=obj)

    # Create all Accounts
    async for node, _ in batch.execute():
        log.info(f"{node._schema.kind} Created {node.name.value}")

    account_eng = store.get("Engineering Team")

    # ------------------------------------------
    # Create Roles, Status & Tags
    # ------------------------------------------
    batch = await client.create_batch()

    log.info("Creating Role, Status & Tag")

    for role in RR_ROLES:
        obj = await client.create(branch=branch, kind="BuiltinRole", name={"value": role, "source": account_eng.id})
        batch.add(task=obj.save, node=obj)
        store.set(key=role, node=obj)

    for status in STATUSES:
        obj = await client.create(branch=branch, kind="BuiltinStatus", name={"value": status, "source": account_eng.id})
        batch.add(task=obj.save, node=obj)
        store.set(key=status, node=obj)

    for tag in TAGS:
        obj = await client.create(branch=branch, kind="BuiltinTag", name={"value": tag, "source": account_eng.id})
        batch.add(task=obj.save, node=obj)
        store.set(key=tag, node=obj)

    async for node, _ in batch.execute():
        log.info(f"{node._schema.kind}  Created {node.name.value}")

    # ------------------------------------------
    # Create Sites
    # ------------------------------------------
    log.info("Creating Site")

    batch = await client.create_batch()

    for site_name in SITE_NAMES:
        batch.add(task=generate_site, site_name=site_name, client=client, branch=branch, log=log)

    async for _, response in batch.execute():
        log.debug(f"Site {response} Creation Completed")

    # ------------------------------------------
    # Create Route Reflectos & IP Address
    # ------------------------------------------
    log.info("Creating Route Reflector")

    for idx, rr in enumerate(ROUTE_REFLECTORS):
        rr_name = f"{site_name}-{rr[0]}"
        rr_status = store.get(kind="BuiltinStatus", key=rr[1]).id
        rr_type = rr[2]
        rr_role = store.get(kind="BuiltinRole", key=rr[3]).id
        tt_tags = [store.get(kind="BuiltinTag", key=tag_name).id for tag_name in rr[4]]
        rr_site = rr[5]
        rr_ip_address = rr[6]

        ip = await client.create(
            branch=branch,
            kind="InfraIPAddress",
            address={"value": f"{str(rr_ip_address)}/32", "source": account_eng.id},
        )
        await ip.save()

        obj = await client.create(
            branch=branch,
            kind="InfraRouteReflector",
            name={"value": rr_name, "source": account_eng.id, "is_protected": True},
            status={"id": rr_status, "owner": account_eng.id},
            type={"value": rr_type, "source": account_eng.id},
            role={"id": rr_role, "source": account_eng.id, "is_protected": True, "owner": account_eng.id},
            tags=tt_tags,
            site={"id": rr_site.id, "source": account_eng.id, "is_protected": True},
            ip_address=store.get(kind="InfraIPAddress", key=rr_ip_address).id,
        )
        await obj.save()

        store.set(key=rr_name, node=obj)
        log.info(f"- Created Route Reflector: {rr_name} with IP: {rr_ip_address}")
