import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional

import docker
from attr import dataclass
from docker.models.containers import Container
from docker.models.networks import Network
from rich.console import Console

from infrahub import config
from infrahub.database import InfrahubDatabase


class DatabaseContainerNotFound(Exception):
    ...


class DatabaseRestoreError(Exception):
    ...


@dataclass
class ContainerDetails:
    container: Container
    networks: List[Network]

    @property
    def name(self) -> str:
        return self.container.name


class Neo4jBackupRestoreBase:
    container_backup_dir = "/neo4jbackups"
    backup_helper_container_name = "neo4j-backup-helper"

    def __init__(self) -> None:
        self.docker_client = docker.from_env()
        self.console = Console()
        self.database_container_details: Optional[ContainerDetails] = None
        self.neo4j_docker_image = os.getenv("NEO4J_DOCKER_IMAGE", "neo4j:5.16.0-enterprise")

    def _get_database_container_details(self, raise_error_on_fail: bool = True) -> Optional[ContainerDetails]:
        if self.database_container_details is None:
            containers = self.docker_client.containers.list(filters={"label": "infrahub_role=database"})
            if len(containers) == 0:
                if raise_error_on_fail:
                    raise DatabaseContainerNotFound("No running container with label infrahub_role=database")
                return None
            if len(containers) > 1:
                if raise_error_on_fail:
                    raise DatabaseContainerNotFound(
                        "Multiple running containers with label infrahub_role=database, expected one"
                    )
                return None
            database_container = containers[0]
            networks = self.docker_client.networks.list(
                names=list(database_container.attrs["NetworkSettings"]["Networks"].keys())
            )
            self.database_container_details = ContainerDetails(container=database_container, networks=networks)
        return self.database_container_details

    def _create_helper_container(
        self, local_backup_directory: Path, local_docker_networks: Optional[List[Network]]
    ) -> Container:
        try:
            existing_exporter_container = self.docker_client.containers.get(self.backup_helper_container_name)
            self.console.print("Existing export container found, removing")
            existing_exporter_container.stop()
            existing_exporter_container.remove()
        except docker.errors.NotFound:
            pass
        self.console.print("Starting new export container")
        backup_helper_container = self.docker_client.containers.run(
            volumes={local_backup_directory.absolute(): {"bind": self.container_backup_dir, "mode": "rw"}},
            name=self.backup_helper_container_name,
            image=self.neo4j_docker_image,
            tty=True,
            detach=True,
            command="/bin/bash",
        )

        if local_docker_networks:
            for network in local_docker_networks:
                network.connect(backup_helper_container)
        return backup_helper_container


class Neo4jBackupRunner(Neo4jBackupRestoreBase):
    def _run_backup(
        self,
        helper_container: Container,
        database_url: str,
        database_backup_port: int,
        do_aggregate_backup: bool = False,
    ) -> None:
        self.console.print("Starting neo4j database backup")
        backup_command = [
            "neo4j-admin",
            "database",
            "backup",
            "*",
            f"--to-path={self.container_backup_dir}",
            f"--from={database_url}:{database_backup_port}",
        ]
        exit_code, response = helper_container.exec_run(backup_command, stdout=True, stderr=True)

        if exit_code != 0:
            self.console.print("[red]neo4j backup command failed")
            self.console.print(f"    export command: {' '.join(backup_command)}")
            self.console.print("    response:")
            self.console.print(response.decode())
            sys.exit(exit_code)
        self.console.print("Neo4j database backup complete")

        if not do_aggregate_backup:
            return

        self.console.print("Aggregating neo4j database backups")
        aggregate_command = [
            "neo4j-admin",
            "database",
            "aggregate-backup",
            f"--from-path={self.container_backup_dir}",
            "*",
        ]
        exit_code, response = helper_container.exec_run(aggregate_command, stdout=True, stderr=True)

        if exit_code != 0:
            self.console.print("[red]neo4j aggregate backups command failed")
            self.console.print(f"    aggregate backups command: {' '.join(aggregate_command)}")
            self.console.print("    response:")
            self.console.print(response.decode())
            sys.exit(exit_code)
        self.console.print("Neo4j database backup aggregation complete")

    async def backup(
        self,
        local_backup_directory: Path,
        database_url: Optional[str],
        database_backup_port: int,
        do_aggregate_backups: bool = True,
    ) -> None:
        local_database_container = self._get_database_container_details(raise_error_on_fail=False)
        local_docker_networks = None
        if local_database_container:
            local_docker_networks = local_database_container.networks
        backup_helper_container = self._create_helper_container(
            local_backup_directory, local_docker_networks=local_docker_networks
        )
        if local_database_container and not database_url:
            database_url = local_database_container.name
        if not database_url:
            raise DatabaseContainerNotFound(
                "Remote database IP address is required when there is no local database container with label 'infrahub_role=database' running"
            )
        self._run_backup(
            backup_helper_container, database_url, database_backup_port, do_aggregate_backup=do_aggregate_backups
        )
        self.console.print(f"Updated backup files are in {local_backup_directory.absolute()}")


class Neo4jRestoreRunner(Neo4jBackupRestoreBase):
    def __init__(self, db: InfrahubDatabase) -> None:
        super().__init__()
        self.db = db

    def _map_backups_to_database_name(self, local_backup_directory: Path) -> Dict[str, Path]:
        # expects name format of <database_name>-2024-02-07T22-12-16.backup
        backup_map = {}
        for backup_path in local_backup_directory.iterdir():
            if not backup_path.suffix == ".backup":
                continue
            split_name = backup_path.name.split("-")
            database_name = "-".join(split_name[:-5])
            backup_map[database_name] = backup_path
        return backup_map

    @asynccontextmanager
    async def _stopped_database(self, database_name: str) -> AsyncGenerator[None, None]:
        self.console.print(f"Stopping '{database_name}' database")
        query = f"STOP DATABASE {database_name}"
        await self.db.execute_query(query)

        try:
            yield
        finally:
            self.console.print(f"Starting '{database_name}' database")
            query = f"START DATABASE {database_name}"
            await self.db.execute_query(query)

    async def _restore_one_database(
        self, database_name: str, database_container_name: str, backup_path: Path, backup_helper_container: Container
    ) -> None:
        async with self._stopped_database(database_name):
            self.console.print(f"Beginning restore for '{database_name}' database")

            remote_path = Path(self.container_backup_dir) / backup_path.name
            restore_command = [
                "neo4j-admin",
                "database",
                "restore",
                f"--from-path={remote_path}",
                "--overwrite-destination=true",
                database_name,
            ]
            exit_code, response = backup_helper_container.exec_run(restore_command, stdout=True, stderr=True)

            if exit_code != 0:
                self.console.print(f"[red]neo4j restore command failed for '{database_name}' database")
                self.console.print(f"    restore command: {' '.join(restore_command)}")
                self.console.print("    response:")
                self.console.print(response.decode())
                raise DatabaseRestoreError(f"Failed to restore database '{database_name}'")

            query = f"CREATE DATABASE {database_name} IF NOT EXISTS"
            await self.db.execute_query(query)

            self.console.print(f"[green]Restore for '{database_name}' database complete!")

        restore_metadata_command = [
            "cat",
            f"/var/lib/neo4j/data/scripts/{database_name}/restore_metadata.cypher",
            "|",
            "bin/cypher-shell",
            "-u <database username>",
            "-p <database password>",
            f"-a {database_container_name}:{config.SETTINGS.database.port}",
            "-d system",
            f"--param \"database => '{database_name}'\"",
        ]
        self.console.print("\n[yellow on black]ATTENTION!")
        self.console.print(
            f"To restore user and role metadata for the '{database_name}' database, you must execute the following "
            f"shell command in the '{self.backup_helper_container_name}' container"
        )
        self.console.print("\n" + " ".join(restore_metadata_command) + "\n")

    async def _run_restore(
        self, database_container: Container, backup_helper_container: Container, backup_path_map: Dict[str, Path]
    ) -> None:
        system_backup_path = None
        for database_name, local_path in backup_path_map.items():
            if database_name == "system":
                system_backup_path = local_path
                continue
            await self._restore_one_database(
                database_name, database_container.name, local_path, backup_helper_container
            )
        if not system_backup_path:
            return

        self.console.print("Beginning restore for 'system' database")
        remote_path = Path(self.container_backup_dir) / system_backup_path.name
        restore_command = [
            "neo4j-admin",
            "database",
            "restore",
            f"--from-path={remote_path}",
            "--overwrite-destination=true",
            "system",
        ]
        exit_code, response = backup_helper_container.exec_run(restore_command, stdout=True, stderr=True)
        if exit_code != 0:
            self.console.print("[red]neo4j restore command failed for 'system' database")
            self.console.print(f"    restore command: {' '.join(restore_command)}")
            self.console.print("    response:")
            self.console.print(response.decode())
            sys.exit(exit_code)
        return

    async def restore(self, local_backup_directory: Path) -> None:
        backup_paths_by_database_name = self._map_backups_to_database_name(local_backup_directory)
        if not backup_paths_by_database_name:
            self.console.print(f"[red]No .backup files in {local_backup_directory} to use for restore")
            sys.exit(1)
        database_container_details = self._get_database_container_details()
        if not database_container_details:
            raise DatabaseContainerNotFound("No running container with label infrahub_role=database")
        if not database_container_details.networks:
            raise DatabaseContainerNotFound(
                f"Database container {database_container_details.name} must be connected to at least one docker network"
            )
        backup_helper_container = self._create_helper_container(
            local_backup_directory, local_docker_networks=database_container_details.networks
        )
        await self._run_restore(
            database_container_details.container, backup_helper_container, backup_paths_by_database_name
        )
        self.console.print("[green]Restore completed successfully")
