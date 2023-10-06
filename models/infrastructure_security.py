import logging
import uuid
import random
from collections import defaultdict
from slugify import slugify
from ipaddress import IPv4Interface, IPv4Network
from typing import Dict, List

from infrahub_client import UUIDT, InfrahubClient, InfrahubNode, NodeStore

# flake8: noqa
# pylint: skip-file

ROLES = ["role11", "role21", "role31"]
STATUSES = ["reserved", "provisionning", "production", "mainteance", "obsolete"]
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
)

PROTOCOLS = (
    # (name, description)
    ("TCP", "TCP"),
    ("UDP", "UDP"),
    ("ICMP", "ICMP"),
)

SERVICES = (
    # name, description, port, ip_protocol
    ("HTTPS", "TCP 443", 443, "TCP"),
    ("REDIS", "TCP 6379", 6379, "TCP"),
)

INTERNAL_IPS = list(IPv4Network("192.0.2.0/29").hosts())
EXTERNAL_IPS = list(IPv4Network("203.0.113.0/29").hosts())

INTERNAL_PREFIXES = IPv4Network("192.0.2.128/25").subnets(new_prefix=29)

store = NodeStore()

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
            branch  =branch, kind="CoreOrganization", data={"name": {"value": org, "is_protected": True}}
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=org[0], node=obj)

    # async for node, _ in batch.execute():
    #     log.info(f"{node._schema.kind} Created {node.name.value}")

    account_security = store.get("security-builder")
    account_john = store.get("John Doe")

    # ------------------------------------------
    # Create Status, Role & Tags
    # ------------------------------------------
    batch = await client.create_batch()

    log.info("Creating Roles, Status & Tag")
    for role in ROLES:
        obj = await client.create(branch=branch, kind="BuiltinRole", name={"value": role, "source": account_security.id})
        batch.add(task=obj.save, node=obj)
        store.set(key=role, node=obj)

    for status in STATUSES:
        obj = await client.create(branch=branch, kind="BuiltinStatus", name={"value": status, "source": account_security.id})
        batch.add(task=obj.save, node=obj)
        store.set(key=status, node=obj)

    for tag in TAGS:
        obj = await client.create(branch=branch, kind="BuiltinTag", name={"value": tag, "source": account_security.id})
        batch.add(task=obj.save, node=obj)
        store.set(key=tag, node=obj)

    # async for node, _ in batch.execute():
    #     log.info(f"{node._schema.kind}  Created {node.name.value}")

    production_status = store.get(kind="BuiltinStatus", key="production")

    # ------------------------------------------
    # Create Applications & Protocols
    # ------------------------------------------
    batch = await client.create_batch()

    log.info("Creating Applications & Protocols")
    for application in APPLICATIONS:
        obj = await client.create(
            branch=branch,
            kind="SecurityApplication",
            data={"name": application[0], "application": application[1], "status": random.choice(STATUSES), "source": account_security.id},
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
    
    for service in SERVICES:
        protocol = store.get(service[3])
        obj = await client.create(
            branch=branch,
            kind="SecurityService",
            data={"name": service[0], "status": random.choice(STATUSES), "description": service[1], "port": service[2], "ip_protocol": protocol, "source": account_security.id},
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=service[0], node=obj)

    # async for node, _ in batch.execute():
    #     log.info(f"{node._schema.kind} Created {node.name.value}")


    # ------------------------------------------
    # Create IPAddresses, Prefixes, IP Ranges & FQDN
    # ------------------------------------------
    batch = await client.create_batch()

    # log.info("Creating IP, Prefixes, Ranges & FQDN")
    for ip_address in INTERNAL_IPS + EXTERNAL_IPS:
        obj = await client.create(
            branch=branch,
            kind="InfraIPAddress",
            data={"address": IPv4Interface(ip_address), "status": random.choice(STATUSES), "source": account_security.id},
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=ip_address, node=obj)

    chunked_ips = []
    for i in range(0, len(INTERNAL_IPS), 2):
        chunked_ips.append(INTERNAL_IPS[i:i+2])

    for range_ips in chunked_ips:
        start_address = store.get(kind="BuiltinStatus", key=range_ips[0])
        end_address = store.get(kind="BuiltinStatus", key=range_ips[len(range_ips)-1])

        range_name = f"range-{range_ips[0]}-{range_ips[len(range_ips)-1]}"
        range_obj = await client.create(
            branch=branch,
            kind="SecurityIPRange",
            data={"name": range_name, "start_address": start_address, "end_address": end_address, "status": random.choice(STATUSES), "source": account_security.id},
        )
        batch.add(task=range_obj.save, node=range_obj)
        store.set(key=range_name, node=range_obj)

    for prefix in INTERNAL_PREFIXES:
        obj = await client.create(
            branch=branch,
            kind="InfraPrefix",
            data={"prefix": prefix, "name": f"net-{slugify(str(prefix))}", "status": random.choice(STATUSES), "source": account_security.id},
        )
        batch.add(task=obj.save, node=obj)
        store.set(key=prefix, node=obj)
    
    async for node, _ in batch.execute():
        if node._schema.kind == "InfraIPAddress":
            log.info(f"{node._schema.kind} Created {node.address.value}")
        elif node._schema.kind == "InfraPrefix":
            log.info(f"{node._schema.kind} Created {node.prefix.value}")
        else:
            log.info(f"{node._schema.kind} Created {node.name.value}")
