import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Dict, Generator, List, Optional

import docker
from docker.models.containers import Container
from docker.models.networks import Network


class DatabaseContainerNotFound(Exception):
    ...


class DatabaseRestoreError(Exception):
    ...


class MissingCredentialsError(Exception):
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
    backup_helper_container_name = "neo4j-infrahub-helper"

    def __init__(self, be_quiet: bool = False, keep_helper_container: bool = False) -> None:
        self.be_quiet = be_quiet
        self.keep_helper_container = keep_helper_container
        self.docker_client = docker.from_env()
        self.neo4j_docker_image = os.getenv("NEO4J_DOCKER_IMAGE", "neo4j:5.16.0-enterprise")

    def _print_message(self, message: str, is_error: bool = False) -> None:
        if self.be_quiet and not is_error:
            return
        print(message)

    @contextmanager
    def _print_task_status(self, start: str, completion_message: Optional[str] = None) -> Generator[None, None, None]:
        end = "" if completion_message else "\n"
        print(start, end=end)
        yield
        if completion_message:
            print(completion_message)

    def _execute_docker_container_command(
        self,
        container: Container,
        command: List[str],
        environment: Optional[Dict[str, str]] = None,
        failure_message: Optional[str] = None,
        display_error: bool = True,
        continue_on_error: bool = False,
    ) -> bool:
        exit_code, response = container.exec_run(command, environment=environment)
        if exit_code == 0:
            return True
        if display_error:
            if failure_message:
                self._print_message(failure_message, is_error=True)
            self._print_message(f"    command: {command}", is_error=True)
            self._print_message("    response:", is_error=True)
            self._print_message(response.decode(), is_error=True)
        if not continue_on_error:
            sys.exit(exit_code)
        return False

    def _get_database_container_details(self, raise_error_on_fail: bool = True) -> Optional[ContainerDetails]:
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
        return ContainerDetails(container=database_container, networks=networks)

    def _create_helper_container(
        self,
        local_backup_directory: Path,
        local_docker_networks: Optional[List[Network]],
        extra_volumes: Optional[Dict[Path, str]] = None,
    ) -> Container:
        try:
            existing_exporter_container = self.docker_client.containers.get(self.backup_helper_container_name)
            self._print_message("Existing export container found, removing")
            existing_exporter_container.stop()
            existing_exporter_container.remove()
        except docker.errors.NotFound:
            pass

        volumes = {local_backup_directory.absolute(): {"bind": self.container_backup_dir, "mode": "rw"}}
        if extra_volumes:
            for local_path, container_path in extra_volumes.items():
                volumes[local_path.absolute()] = {"bind": container_path, "mode": "rw"}
        with self._print_task_status("Starting new helper container...", "[green]Done"):
            backup_helper_container = self.docker_client.containers.run(
                volumes=volumes,
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
    backup_helper_container_name = "neo4j-backup-helper"

    def _run_backup(
        self,
        helper_container: Container,
        database_url: str,
        database_backup_port: int,
        do_aggregate_backup: bool = False,
    ) -> None:
        with self._print_task_status("Starting neo4j database backup...", "[green]Done!"):
            backup_command = [
                "neo4j-admin",
                "database",
                "backup",
                "*",
                f"--to-path={self.container_backup_dir}",
                f"--from={database_url}:{database_backup_port}",
            ]
            self._execute_docker_container_command(
                helper_container,
                backup_command,
                failure_message="neo4j backup command failed",
            )

        if not do_aggregate_backup:
            return

        with self._print_task_status("Aggregating neo4j database backups...", "[green]Done!"):
            aggregate_command = [
                "neo4j-admin",
                "database",
                "aggregate-backup",
                f"--from-path={self.container_backup_dir}",
                "*",
            ]
            self._execute_docker_container_command(
                helper_container,
                aggregate_command,
                failure_message="neo4j aggregate backups command failed",
            )

    def backup(
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
        self._print_message(f"Updated backup files are in {local_backup_directory.absolute()}")
        if not self.keep_helper_container:
            backup_helper_container.stop()
            backup_helper_container.remove()


class Neo4jRestoreRunner(Neo4jBackupRestoreBase):
    container_scripts_dir = "/neo4jscripts"
    backup_helper_container_name = "neo4j-restore-helper"

    def __init__(self, *args, database_cypher_port: int = 7687, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.database_cypher_port = database_cypher_port
        neo4j_auth = os.environ.get("NEO4J_AUTH")
        if not neo4j_auth:
            raise MissingCredentialsError("Must set environment variable NEO4J_AUTH=username/password")
        self.database_username, self.database_password = neo4j_auth.split("/")

    def _execute_cypher_command(
        self,
        execution_container: Container,
        database_container: Container,
        local_scripts_dir: Path,
        command: str,
        against_database: str = "system",
    ) -> None:
        environment = {"NEO4J_USERNAME": self.database_username, "NEO4J_PASSWORD": self.database_password}
        with NamedTemporaryFile(dir=local_scripts_dir) as script_file:
            script_file.write(command.encode())
            script_file.seek(0)
            script_path = Path(script_file.name)
            cypher_command = f"cat {self.container_scripts_dir}/{script_path.name} | bin/cypher-shell"
            cypher_command += f" -a {database_container.name}:{self.database_cypher_port} -d {against_database}"
            full_command = ["sh", "-c", cypher_command]
            self._execute_docker_container_command(
                execution_container, full_command, environment=environment, display_error=False, continue_on_error=True
            )

    def _execute_restore_metadata_command(
        self,
        execution_container: Container,
        database_container: Container,
        database_name: str,
    ) -> None:
        with self._print_task_status(f"Restoring '{database_name}' database metadata...", "Done!"):
            environment = {"NEO4J_USERNAME": self.database_username, "NEO4J_PASSWORD": self.database_password}
            metadata_file_path = f"/var/lib/neo4j/data/scripts/{database_name}/restore_metadata.cypher"

            cypher_command = f"cat {metadata_file_path} | bin/cypher-shell"
            cypher_command += f" -a {database_container.name}:{self.database_cypher_port}"
            cypher_command += f" -d system --param \"database => '{database_name}'\""
            full_command = ["sh", "-c", cypher_command]
            self._execute_docker_container_command(
                execution_container,
                full_command,
                environment=environment,
                failure_message="neo4j metadata restore command failed for '{database_name}' database",
                display_error=True,
                continue_on_error=True,
            )

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

    @contextmanager
    def _stopped_database(
        self, helper_container: Container, database_container: Container, database_name: str, local_scripts_dir: Path
    ) -> Generator[None, None, None]:
        with self._print_task_status(f"Stopping '{database_name}' database...", "stopped"):
            database_command = f"STOP DATABASE {database_name}"
            self._execute_cypher_command(helper_container, database_container, local_scripts_dir, database_command)
        try:
            yield
        finally:
            with self._print_task_status(f"Restarting '{database_name}' database...", "started"):
                database_command = f"START DATABASE {database_name}"
                breakpoint()
                self._execute_cypher_command(helper_container, database_container, local_scripts_dir, database_command)

    def _restore_one_database(
        self,
        database_name: str,
        database_container: Container,
        backup_path: Path,
        helper_container: Container,
        local_scripts_dir: Path,
    ) -> None:
        with self._stopped_database(helper_container, database_container, database_name, local_scripts_dir):
            with self._print_task_status(f"Beginning restore for '{database_name}' database...", "[green]Complete!"):
                remote_path = Path(self.container_backup_dir) / backup_path.name
                restore_command = [
                    "neo4j-admin",
                    "database",
                    "restore",
                    f"--from-path={remote_path}",
                    "--overwrite-destination=true",
                    database_name,
                ]
                success = self._execute_docker_container_command(
                    helper_container,
                    restore_command,
                    failure_message="neo4j restore command failed for '{database_name}' database",
                    display_error=True,
                    continue_on_error=True,
                )
                if not success:
                    raise DatabaseRestoreError(f"Failed to restore database '{database_name}'")

                database_command = f"CREATE DATABASE {database_name} IF NOT EXISTS"
                self._execute_cypher_command(helper_container, database_container, local_scripts_dir, database_command)

        self._execute_restore_metadata_command(helper_container, database_container, database_name)

    def _run_restore(
        self,
        database_container: Container,
        helper_container: Container,
        backup_path_map: Dict[str, Path],
        local_scripts_dir: Path,
    ) -> None:
        system_backup_path = None
        for database_name, local_path in backup_path_map.items():
            if database_name == "system":
                system_backup_path = local_path
                continue
            self._restore_one_database(
                database_name, database_container, local_path, helper_container, local_scripts_dir
            )
        if not system_backup_path:
            return

        with self._print_task_status("Beginning restore for 'system' database...", "[green]Complete!"):
            remote_path = Path(self.container_backup_dir) / system_backup_path.name
            restore_command = [
                "neo4j-admin",
                "database",
                "restore",
                f"--from-path={remote_path}",
                "--overwrite-destination=true",
                "system",
            ]
            self._execute_docker_container_command(
                helper_container,
                restore_command,
                failure_message="neo4j restore command failed for 'system' database",
                display_error=True,
                continue_on_error=False,
            )

    def restore(self, local_backup_directory: Path) -> None:
        backup_paths_by_database_name = self._map_backups_to_database_name(local_backup_directory)
        if not backup_paths_by_database_name:
            self._print_message(f"[red]No .backup files in {local_backup_directory} to use for restore", is_error=True)
            sys.exit(1)
        database_container_details = self._get_database_container_details()
        if not database_container_details:
            raise DatabaseContainerNotFound("No running container with label infrahub_role=database")
        if not database_container_details.networks:
            raise DatabaseContainerNotFound(
                f"Database container {database_container_details.name} must be connected to at least one docker network"
            )
        with TemporaryDirectory() as scripts_dir:
            scripts_path = Path(scripts_dir)
            helper_container = self._create_helper_container(
                local_backup_directory,
                local_docker_networks=database_container_details.networks,
                extra_volumes={scripts_path: self.container_scripts_dir},
            )
            self._run_restore(
                database_container_details.container, helper_container, backup_paths_by_database_name, scripts_path
            )
        self._print_message("[green]Restore completed successfully", is_error=True)

        if not self.keep_helper_container:
            helper_container.stop()
            helper_container.remove()
