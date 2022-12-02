import os
import time

from typing import Generator
from neo4j import GraphDatabase, basic_auth, Driver, Session

# from contextlib import asynccontextmanager
from neo4j.exceptions import ClientError

import infrahub.config as config

from .metrics import QUERY_READ_METRICS, QUERY_WRITE_METRICS


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
            db = driver.session(database=config.SETTINGS.database.database)
            results = db.run("SHOW TRANSACTIONS")
            validated_database[config.SETTINGS.database.database] = True

        except ClientError as exc:
            if "database does not exist" in exc.message:

                default_db = driver.session()
                results = default_db.run(f"CREATE DATABASE {config.SETTINGS.database.database}")

                # TODO Catch possible exception here

            else:
                raise

    db = driver.session(database=config.SETTINGS.database.database)

    # FIXME should be enclosed in try/finally block but somehow it is not working right now
    yield db

    db.close()


@QUERY_READ_METRICS.time()
def execute_read_query(query: str, params: dict = None, session: Session = None):

    if not session:
        session: Session = next(get_db())

    response = session.run(query, params)
    return list(response)


@QUERY_WRITE_METRICS.time()
def execute_write_query(query: str, params: dict = None, session: Session = None):

    if not session:
        session: Session = next(get_db())

    response = session.run(query, params)
    return list(response)
