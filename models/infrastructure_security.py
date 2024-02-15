import logging
import random
from ipaddress import IPv4Interface, IPv4Network

from infrahub_sdk import InfrahubClient, InfrahubNode, NodeStore

# flake8: noqa
# pylint: skip-file

ROLES = ["role11", "role21", "role31"]
STATUSES = ["reserved", "provisioning", "active", "maintenance", "obsolete"]
TAGS = ["blue", "green", "red", "tenant", "provider"]

ORGANIZATIONS = (
    # name
    "Tenant",
    "Provider",
)

ACCOUNTS = (
    # (name, type, password, rights)
    ("security-builder", "Script", "Password123", "read-write"),
    ("John Doe", "User", "Password123", "read-write"),
)

APPLICATIONS = (
    # (name, description)
    ("Infrahub-client", "Infrahub Client"),
    ("Infrahub-api", "Infrahub Api"),
    ("Infrahub-redis", "Infrahub Redis"),
    ("Domain-controller", "Domain Controller"),
    ("DNS", "DNS Authoritative Server"),
    ("docker", "Docker"),
    ("Gitlab", "Gitlab Server"),
)

PROTOCOLS = (
    # (name, description)
    ("TCP", "TCP"),
    ("UDP", "UDP"),
    ("ICMP", "ICMP"),
)

SERVICES = (
    # name, description, port, ip_protocol, status
    ("HTTPS", "TCP 443", 443, "TCP", "active"),
    ("REDIS", "TCP 6379", 6379, "TCP", "active"),
    ("SSH", "TCP 22", 33, "TCP", "active"),
    ("DNS UDP", "UDP 53", 53, "UDP", "active"),
    ("DNS TCP", "TCP 53", 53, "TCP", "provisioning"),
)

EXTERNAL_IPS = list(IPv4Network("203.0.113.0/29").hosts())

INTERNAL_PREFIXES = (
    # name, prefix, Status
    ("office-nyc", "192.168.0.0/16", "active"),
    ("datacenter-eu-fr", "172.16.0.0/20", "active"),
    ("datacenter-eu-de", "172.16.16.0/20", "provisioning"),
    ("datacenter-us-ny", "172.16.32.0/20", "reserved"),
)

INTERNAL_RANGES = (
    # name, start IP, end IP, Status
    ("office-nyc-printer", "192.168.0.1/24", "192.168.0.9/24", "active"),
    ("office-nyc-wifi", "192.168.1.10/24", "192.168.1.250/24", "active"),
    ("office-nyc-users", "192.168.0.10/24", "192.168.0.200/24", "obsolete"),
)

FQDNS = (
    # name
    ("redis.example.com", ""),
    ("website.example.com", ""),
    ("www.example.com", ""),
    ("opsmill.com", ""),
    ("google.com", ""),
    ("docker.com", ""),
)

RULES = (
    # Index, Name, Action, Description, Source Addresses, Destination Addresses, Source Services, Destination Services, Source Applications, Destination Applications, Status
    (
        1,
        "dns-office-to-dc",
        "Accept",
        None,
        ("office-nyc",),
        (
            "datacenter-eu-fr",
            "datacenter-eu-de",
        ),
        ("DNS UDP",),
        None,
        None,
        None,
        "active",
    ),
    (
        2,
        "https-eu-fr-to-docker.com",
        "Accept",
        None,
        ("datacenter-eu-fr",),
        ("docker.com",),
        ("HTTPS",),
        None,
        ("docker",),
        None,
        "active",
    ),
    (
        3,
        "web-nt-wifi-and-dc-to-eu-fr",
        "Accept",
        None,
        (
            "office-nyc-wifi",
            "datacenter-us-ny",
        ),
        ("datacenter-eu-fr",),
        ("HTTPS",),
        None,
        ("Infrahub-api", "Gitlab"),
        None,
        "active",
    ),
)

store = NodeStore()


def prepare_log(node: InfrahubNode, log: logging.Logger) -> None:
    if node._schema.kind == "InfraIPAddress":
        log.info(f"{node._schema.kind} Created {node.address.value}")
    elif node._schema.kind == "InfraPrefix":
        log.info(f"{node._schema.kind} Created {node.prefix.value}")
    else:
        log.info(f"{node._schema.kind} Created {node.name.value}")


async def create_infra_ip(client, branch, name, address, statuses, source, batch):
    obj = await client.create(
        branch=branch,
        kind="InfraIPAddress",
        data={"name": name, "address": IPv4Interface(address), "status": random.choice(statuses), "source": source},
    )
    batch.add(task=obj.save, node=obj)
    store.set(key=name, node=obj)


# ---------------------------------------------------------------
# Use the `infrahubctl run` command line to execute this script
#
#   infrahubctl run models/infrastructure_edge.py
#
# ---------------------------------------------------------------
async def run(client: InfrahubClient, log: logging.Logger, branch: str):
    # ------------------------------------------
    # Create User Accounts, Groups & Organizations & Platforms
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

    for org in ORGANIZATIONS:
        obj = await client.create(
            branch=branch, kind="CoreOrganization", data={"name": {"value": org, "is_protected": True}}
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=org[0], node=obj)

    async for node, _ in batch.execute():
        prepare_log(node, log)

    account_security = store.get("security-builder")
    store.get("John Doe")

    # ------------------------------------------
    # Create Status, Role & Tags
    # ------------------------------------------
    batch = await client.create_batch()

    log.info("Creating Roles, Status & Tag")
    for role in ROLES:
        obj = await client.create(
            branch=branch, kind="BuiltinRole", name={"value": role, "source": account_security.id}
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=role, node=obj)

    for status in STATUSES:
        obj = await client.create(
            branch=branch, kind="BuiltinStatus", name={"value": status, "source": account_security.id}
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=status, node=obj)

    for tag in TAGS:
        obj = await client.create(branch=branch, kind="BuiltinTag", name={"value": tag, "source": account_security.id})
        batch.add(task=obj.save, node=obj)
        store.set(key=tag, node=obj)

    async for node, _ in batch.execute():
        prepare_log(node, log)

    # ------------------------------------------
    # Create Applications & Protocols
    # ------------------------------------------
    batch = await client.create_batch()

    log.info("Creating Applications & Protocols")
    for application in APPLICATIONS:
        obj = await client.create(
            branch=branch,
            kind="SecurityApplication",
            data={
                "name": application[0],
                "application": application[1],
                "status": random.choice(STATUSES),
                "source": account_security.id,
            },
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=application[0], node=obj)

    for protocol in PROTOCOLS:
        obj = await client.create(
            branch=branch,
            kind="SecurityProtocol",
            data={"name": protocol[0], "description": protocol[1], "source": account_security.id},
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=protocol[0], node=obj)

    async for node, _ in batch.execute():
        prepare_log(node, log)

    # ------------------------------------------
    # Create Services
    # ------------------------------------------
    batch = await client.create_batch()

    log.info("Creating Services")
    for service in SERVICES:
        obj = await client.create(
            branch=branch,
            kind="SecurityService",
            data={
                "name": service[0],
                "status": store.get(key=service[3], kind="BuiltinStatus"),
                "description": service[1],
                "port": service[2],
                "ip_protocol": store.get(key=service[3], kind="SecurityProtocol"),
                "source": account_security.id,
            },
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=service[0], node=obj)

    async for node, _ in batch.execute():
        prepare_log(node, log)

    # ------------------------------------------
    # Create IP Address, FQDNs Prefix
    # ------------------------------------------
    batch = await client.create_batch()

    log.info("Creating IP Address, FQDNs Prefix")
    for ip_address in EXTERNAL_IPS:
        await create_infra_ip(client, branch, ip_address, ip_address, STATUSES, account_security.id, batch)

    for ip_range in INTERNAL_RANGES:
        await create_infra_ip(client, branch, ip_range[1], ip_range[1], STATUSES, account_security.id, batch)
        await create_infra_ip(client, branch, ip_range[2], ip_range[2], STATUSES, account_security.id, batch)

    for prefix in INTERNAL_PREFIXES:
        obj = await client.create(
            branch=branch,
            kind="InfraPrefix",
            data={
                "name": prefix[0],
                "prefix": prefix[1],
                "status": store.get(key=prefix[2], kind="BuiltinStatus"),
                "source": account_security.id,
            },
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=prefix[0], node=obj)

    for fqdn in FQDNS:
        obj = await client.create(
            kind="SecurityFQDN",
            data={"name": fqdn[0], "status": random.choice(STATUSES), "source": account_security.id},
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=fqdn[0], node=obj)

    async for node, _ in batch.execute():
        prepare_log(node, log)

    # ------------------------------------------
    # Create IP Ranges
    # ------------------------------------------
    batch = await client.create_batch()

    log.info("Creating IP Ranges")
    for ip_range in INTERNAL_RANGES:
        obj = await client.create(
            branch=branch,
            kind="SecurityIPRange",
            data={
                "name": ip_range[0],
                "start_address": ip_range[1],
                "end_address": ip_range[2],
                "status": store.get(key=ip_range[3], kind="BuiltinStatus"),
                "source": account_security.id,
            },
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=ip_range[0], node=obj)

    async for node, _ in batch.execute():
        prepare_log(node, log)

    # ------------------------------------------
    # Create Rules
    # ------------------------------------------
    batch = await client.create_batch()

    log.info("Creating Security Rules")
    for rule in RULES:
        data = {
            "source": account_security.id,
            "index": rule[0],
            "name": rule[1],
            "action": rule[2],
            "status": store.get(key=rule[10], kind="BuiltinStatus"),
        }
        if rule[3]:
            data["description"] = rule[3]

        # Set Source/Destination Addresses (Prefix, Range, Single IP, FQDN, ..)
        if rule[4]:
            data["source_addresses"] = [store.get(key=item) for item in rule[4]]
        if rule[5]:
            data["destination_addresses"] = [store.get(key=item) for item in rule[5]]

        # Set Source/Destination Services
        if rule[6]:
            data["source_services"] = [store.get(key=item) for item in rule[6]]
        if rule[7]:
            data["destination_services"] = [store.get(key=item) for item in rule[7]]

        # Set Source/Destination Applications
        if rule[8]:
            data["source_applications"] = [store.get(key=item) for item in rule[8]]
        if rule[9]:
            data["destination_applications"] = [store.get(key=item) for item in rule[9]]

        obj = await client.create(branch=branch, kind="SecurityRule", data=data)
        batch.add(task=obj.save, node=obj)
        store.set(key=rule[1], node=obj)

    async for node, _ in batch.execute():
        prepare_log(node, log)
