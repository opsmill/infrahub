import random
import string
from dataclasses import dataclass
from typing import Any, Dict

import docker
from infrahub_sdk import InfrahubClientSync
from neo4j import GraphDatabase
from neo4j.exceptions import DriverError, Neo4jError

from .config import config


@dataclass
class ContainerStats:
    cpu_usage: float
    memory_usage: int


@dataclass
class DbStats:
    node_count: int
    rel_count: int
    db_size: int


def random_ascii_string(length: int = 10) -> str:
    return "".join(random.choice(string.ascii_lowercase) for i in range(length))


def get_container_resource_usage(container_id: str) -> ContainerStats:
    client = docker.from_env()

    try:
        stats = client.containers.get(container_id).stats(stream=False)
    except docker.errors.NotFound:
        raise Exception

    try:
        cpu_usage = get_cpu_usage(stats)
    except KeyError:
        raise Exception

    try:
        memory_usage = get_memory_usage(stats)
    except KeyError:
        raise Exception

    return ContainerStats(cpu_usage, memory_usage)


def get_cpu_usage(stats: Dict[str, Any]) -> float:
    # forked from
    # https://github.com/TomasTomecek/sen/blob/ec292b5a723cd59818e3a36a7ea5091625fb3258/sen/util.py#L162
    cpu_count = stats["cpu_stats"]["online_cpus"]
    cpu_percent = 0.0
    cpu_delta = float(stats["cpu_stats"]["cpu_usage"]["total_usage"]) - float(
        stats["precpu_stats"]["cpu_usage"]["total_usage"]
    )
    system_delta = float(stats["cpu_stats"]["system_cpu_usage"]) - float(stats["precpu_stats"]["system_cpu_usage"])
    if system_delta > 0.0:
        cpu_percent = cpu_delta / system_delta * 100.0 * cpu_count
    return cpu_percent


def get_memory_usage(stats: Dict[str, Any]) -> int:
    return stats["memory_stats"]["usage"]


def get_graphdb_stats() -> DbStats:
    try:
        with GraphDatabase.driver(
            f"{config.db_protocol}://{config.db_host}:{config.db_port}",
            auth=(config.db_username, config.db_password),
            connection_timeout=5,
        ) as driver:
            resp = driver.execute_query(
                """MATCH (n)
WITH count(n) as count
RETURN 'nodes' as label, count
UNION ALL MATCH ()-[r]->()
WITH count(r) as count
RETURN 'relations' as label , count
"""
            )
            node_count, rel_count = resp.records[0].values()[1], resp.records[1].values()[1]
    except (Neo4jError, DriverError):
        node_count, rel_count = 0

    db_size = 0
    client = docker.from_env()
    df_data = client.df()
    for volume in df_data["Volumes"]:
        if volume.get("Name", "") == config.db_volume:
            db_size = volume.get("UsageData", {}).get("Size")

    return DbStats(node_count=node_count, rel_count=rel_count, db_size=db_size)


def prepare_node_attributes(client: InfrahubClientSync) -> dict:
    extra_attributes = dict()
    for i in range(config.attrs_amount):
        extra_attributes[f"attr{i}"] = random_ascii_string()

    # Create a tag to use for relationship
    if config.rels_amount > 0:
        tag = client.create(kind="BuiltinTag", data={"name": random_ascii_string()})
        tag.save()
        for i in range(config.rels_amount):
            extra_attributes[f"rel{i}"] = tag.id

    return extra_attributes
