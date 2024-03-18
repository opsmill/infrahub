import argparse
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Generator, List, Optional

import docker
from docker.models.containers import Container
from docker.models.networks import Network


def parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="Infrahub Database Backup and Restore Utility",
        description="Command line tool for backing up an Infrahub database and restoring it",
    )
    subparsers = parser.add_subparsers(dest="database_type", required=True)
    # memgraph_parser = subparsers.add_parser("memgraph", help="memgraph backup/restore tool")
    neo4j_parser = subparsers.add_parser("neo4j", help="Neo4J backup/restore tool")
    neo4j_subparsers = neo4j_parser.add_subparsers(dest="database_action", required=True)
    neo4j_backup_subparser = neo4j_subparsers.add_parser("backup", help="Backup Neo4J database")
    neo4j_backup_subparser.add_argument(
        "backup_directory", default="infrahub-backups", help="Where to save backup files"
    )
    neo4j_backup_subparser.add_argument(
        "--database-url", default=None, required=False, help="URL of database, null implies a local database container"
    )
    neo4j_backup_subparser.add_argument(
        "--database-backup-port", default=6362, help="Port that the database is listening on for backup commands"
    )
    neo4j_backup_subparser.add_argument(
        "--no-aggregate",
        default=False,
        action="store_true",
        help="Skip backup aggregation, potentially leaving multiple incremental backup files per database",
    )
    neo4j_backup_subparser.add_argument(
        "--quiet", default=False, action="store_true", help="Whether to output status messages to terminal"
    )
    neo4j_backup_subparser.add_argument(
        "--keep-helper-container", default=False, action="store_true", help="Keep docker container used to run backup"
    )
    neo4j_backup_subparser.add_argument(
        "--host-network", default=False, action="store_true", help="Use host network mode for the helper container"
    )

    neo4j_restore_subparser = neo4j_subparsers.add_parser("restore", help="Backup Neo4J database")
    neo4j_restore_subparser.add_argument(
        "backup_directory", default="infrahub-backups", help="Directory where the backup files are saved"
    )
    neo4j_restore_subparser.add_argument(
        "--database-cypher-port",
        default=7687,
        help="Port that the Infrahub database container uses for cypher connections",
    )
    neo4j_restore_subparser.add_argument(
        "--keep-helper-container", default=False, action="store_true", help="Keep docker container used to run restore"
    )
    return parser.parse_args()


def run_utility(parsed_args: argparse.Namespace) -> None:
    if parsed_args.database_type == "memgraph":
        print("Database backup and restore is not yet supported for memgraph")
        return

    backup_path = Path(parsed_args.backup_directory)
    if parsed_args.database_action == "backup":
        backup_runner = Neo4jBackupRunner(
            be_quiet=parsed_args.quiet,
            keep_helper_container=parsed_args.keep_helper_container,
            use_host_network=parsed_args.host_network,
        )
        do_aggregate_backups = not parsed_args.no_aggregate
        backup_runner.backup(
            backup_path,
            parsed_args.database_url,
            parsed_args.database_backup_port,
            do_aggregate_backups=do_aggregate_backups,
        )

    elif parsed_args.database_action == "restore":
        restore_runner = Neo4jRestoreRunner(
            keep_helper_container=parsed_args.keep_helper_container,
            database_cypher_port=parsed_args.database_cypher_port,
        )
        restore_runner.restore(backup_path)


class DatabaseContainerNotFoundError(Exception): ...


class DatabaseRestoreError(Exception): ...


class MissingCredentialsError(Exception): ...


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

    def __init__(
        self, be_quiet: bool = False, keep_helper_container: bool = False, use_host_network: bool = False
    ) -> None:
        self.be_quiet = be_quiet
        self.keep_helper_container = keep_helper_container
        self.docker_client = docker.from_env()
        self.use_host_network = use_host_network
        self.neo4j_docker_image = os.getenv("NEO4J_BACKUP_DOCKER_IMAGE", "neo4j/neo4j-admin:5.16.0-enterprise")

    def _print_message(self, message: str, force_print: bool = False, with_timestamp: bool = True) -> None:
        if self.be_quiet and not force_print:
            return
        if not with_timestamp:
            print(message)
        right_now = datetime.now(timezone.utc).astimezone()
        right_now_str = right_now.strftime("%H:%M:%S")
        print(f"{right_now_str} - {message}")

    @contextmanager
    def _print_task_status(
        self, start: str, completion_message: Optional[str] = None, with_timestamp: bool = True
    ) -> Generator[None, None, None]:
        end = "" if completion_message else "\n"
        to_print = start
        if with_timestamp:
            right_now = datetime.now(timezone.utc).astimezone()
            right_now_str = right_now.strftime("%H:%M:%S")
            to_print = f"{right_now_str} - {start}"
        print(to_print, end=end, flush=True)
        yield
        if completion_message:
            print(completion_message, flush=True)

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
                self._print_message(failure_message, force_print=True)
            self._print_message(f"    command: {command}", force_print=True, with_timestamp=False)
            self._print_message("    response:", force_print=True, with_timestamp=False)
            self._print_message(response.decode(), force_print=True, with_timestamp=False)
        if not continue_on_error:
            sys.exit(exit_code)
        return False

    def _get_database_container_details(self, raise_error_on_fail: bool = True) -> Optional[ContainerDetails]:
        containers = self.docker_client.containers.list(filters={"label": "infrahub_role=database"})
        if len(containers) == 0:
            if raise_error_on_fail:
                raise DatabaseContainerNotFoundError("No running container with label infrahub_role=database")
            return None
        if len(containers) > 1:
            if raise_error_on_fail:
                raise DatabaseContainerNotFoundError(
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
        volumes_from_container_names: Optional[List[str]] = None,
    ) -> Container:
        try:
            existing_exporter_container = self.docker_client.containers.get(self.backup_helper_container_name)
            self._print_message("Existing export container found, removing")
            existing_exporter_container.stop()
            existing_exporter_container.remove()
        except docker.errors.NotFound:
            pass

        volumes = {
            local_backup_directory.absolute(): {"bind": self.container_backup_dir, "mode": "rw"},
        }
        if volumes_from_container_names:
            for c in self.docker_client.containers.list(filters={"status": "running"}):
                if c.name not in volumes_from_container_names:
                    continue
                for v in c.attrs["Mounts"]:
                    if "Name" in v and "Destination" in v:
                        volumes[v["Name"]] = {"bind": v["Destination"], "mode": "rw"}

        with self._print_task_status("Starting new helper container...", "done"):
            backup_helper_container = self.docker_client.containers.run(
                volumes=volumes,
                name=self.backup_helper_container_name,
                image=self.neo4j_docker_image,
                environment={"NEO4J_ACCEPT_LICENSE_AGREEMENT": "yes"},
                tty=True,
                detach=True,
                command="/bin/bash",
                user="neo4j",
                network_mode="host" if self.use_host_network else None,
            )
            for v in volumes.values():
                backup_helper_container.exec_run(["chown", "neo4j", v["bind"]], user="root")

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
        with self._print_task_status("Starting neo4j database backup...", "done"):
            backup_command = [
                "neo4j-admin",
                "database",
                "backup",
                "*",
                f"--to-path={self.container_backup_dir}",
                f"--from={database_url}:{database_backup_port}",
                "--verbose",
            ]
            self._execute_docker_container_command(
                helper_container,
                backup_command,
                failure_message="neo4j backup command failed",
            )

        if not do_aggregate_backup:
            return

        with self._print_task_status("Aggregating neo4j database backups...", "done"):
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
            raise DatabaseContainerNotFoundError(
                "Remote database IP address is required when there is no local database container with label 'infrahub_role=database' running"
            )
        self._run_backup(
            backup_helper_container, database_url, database_backup_port, do_aggregate_backup=do_aggregate_backups
        )
        self._print_message(f"Updated backup files are in {local_backup_directory.absolute()}")
        if not self.keep_helper_container:
            with self._print_task_status("Removing helper container...", "done"):
                backup_helper_container.stop()
                backup_helper_container.remove()


class Neo4jRestoreRunner(Neo4jBackupRestoreBase):
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
        command: str,
        against_database: str = "system",
    ) -> None:
        environment = {"NEO4J_USERNAME": self.database_username, "NEO4J_PASSWORD": self.database_password}
        cypher_command = f'echo "{command}" | bin/cypher-shell'
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
        with self._print_task_status(f"Restoring '{database_name}' database metadata...", "done"):
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
    def _stopped_database(self, database_container: Container, database_name: str) -> Generator[None, None, None]:
        with self._print_task_status(f"Stopping '{database_name}' database...", "stopped"):
            database_command = f"STOP DATABASE {database_name}"
            self._execute_cypher_command(database_container, database_container, database_command)
        try:
            yield
        finally:
            with self._print_task_status(f"Restarting '{database_name}' database...", "started"):
                database_command = f"START DATABASE {database_name}"
                self._execute_cypher_command(database_container, database_container, database_command)

    def _restore_one_database(
        self,
        database_name: str,
        database_container: Container,
        backup_path: Path,
        helper_container: Container,
    ) -> None:
        with self._stopped_database(database_container, database_name):
            with self._print_task_status(f"Beginning restore for '{database_name}' database...", "done"):
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
                    continue_on_error=False,
                )
                if not success:
                    raise DatabaseRestoreError(f"Failed to restore database '{database_name}'")

                database_command = f"CREATE DATABASE {database_name} IF NOT EXISTS"
                self._execute_cypher_command(helper_container, database_container, database_command)

        self._execute_restore_metadata_command(helper_container, database_container, database_name)

    def _run_restore(
        self,
        database_container: Container,
        helper_container: Container,
        backup_path_map: Dict[str, Path],
    ) -> None:
        for database_name, local_path in backup_path_map.items():
            if database_name == "system":
                continue
            self._restore_one_database(database_name, database_container, local_path, helper_container)

    def restore(self, local_backup_directory: Path) -> None:
        backup_paths_by_database_name = self._map_backups_to_database_name(local_backup_directory)
        if not backup_paths_by_database_name:
            self._print_message(
                f"[red]No .backup files in {local_backup_directory} to use for restore", force_print=True
            )
            sys.exit(1)
        database_container_details = self._get_database_container_details()
        if not database_container_details:
            raise DatabaseContainerNotFoundError("No running container with label infrahub_role=database")
        if not database_container_details.networks:
            raise DatabaseContainerNotFoundError(
                f"Database container {database_container_details.name} must be connected to at least one docker network"
            )
        helper_container = self._create_helper_container(
            local_backup_directory,
            local_docker_networks=database_container_details.networks,
            volumes_from_container_names=[database_container_details.name],
        )
        self._run_restore(database_container_details.container, helper_container, backup_paths_by_database_name)
        self._print_message("Restore completed successfully", force_print=True)

        if not self.keep_helper_container:
            with self._print_task_status("Removing helper container...", "done"):
                helper_container.stop()
                helper_container.remove()


if __name__ == "__main__":
    parsed_args = parse()
    run_utility(parsed_args)
