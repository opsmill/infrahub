import os
import time

from typing import Generator
from neo4j import GraphDatabase, basic_auth, Driver, Session

# from contextlib import asynccontextmanager
from neo4j.exceptions import ClientError

import infrahub.config as config

from .metrics import QUERY_READ_METRICS, QUERY_WRITE_METRICS


# Check Database Status
def get_list_queries(tx):
    return list(tx.run("SHOW TRANSACTIONS"))


def create_database(tx, database_name: str):
    return list(tx.run(f"CREATE DATABASE {database_name}"))


NEO4J_PROTOCOL = os.environ.get("NEO4J_PROTOCOL", "neo4j")  # neo4j+s
NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "admin")
NEO4J_ADDRESS = os.environ.get("NEO4J_ADDRESS", "localhost")
NEO4J_PORT = os.environ.get("NEO4J_PORT", 7687)  # 443
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "infrahub")

URL = f"{NEO4J_PROTOCOL}://{NEO4J_ADDRESS}"

driver: Driver = GraphDatabase.driver(URL, auth=basic_auth(NEO4J_USERNAME, NEO4J_PASSWORD))
validated_database = {}


def get_db() -> Generator[Session, None, None]:
    global validated_database

    if config.SETTINGS.database.database not in validated_database:
        try:
            # print(f"Checking if connection is working as expected ({config.SETTINGS.database.database})")
            db = driver.session(database=config.SETTINGS.database.database)
            db.read_transaction(get_list_queries)
            validated_database[config.SETTINGS.database.database] = True

        except ClientError as exc:
            if "database does not exist" in exc.message:
                # print(f"Unable to find the database {config.SETTINGS.database.database}, creating")
                default_db = driver.session()
                # TODO Catch possible exception here
                default_db.write_transaction(create_database, config.SETTINGS.database.database)
            else:
                raise

    db = driver.session(database=config.SETTINGS.database.database)

    try:
        yield db
    finally:
        db.close()


@QUERY_READ_METRICS.time()
def execute_read_query(query: str, params: dict):
    def work(tx, params: dict):
        return list(tx.run(query, params))

    time_start = time.time()
    db: Session = next(get_db())
    results = db.read_transaction(work, params)
    time_end = time.time() - time_start

    if config.SETTINGS.main.print_query_details:
        print(f"Execution Time: {int(time_end*1000)}ms")

    return results


@QUERY_WRITE_METRICS.time()
def execute_write_query(query: str, params: dict):
    def work(tx, params: dict):
        return list(tx.run(query, params))

    db: Session = next(get_db())

    return db.write_transaction(work, params)
