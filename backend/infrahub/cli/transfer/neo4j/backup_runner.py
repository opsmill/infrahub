import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import docker
from docker.models.containers import Container
from rich.console import Console


class Neo4jBackupRunner:
    backup_helper_container_name = "neo4j-backup-helper"
    container_backup_dir = "/tmp/neo4jbackup"

    def __init__(self) -> None:
        self.docker_client = docker.from_env()
        self.console = Console()
        self.neo4j_docker_image = os.getenv("NEO4J_DOCKER_IMAGE", "neo4j:5.16.0-community")
        self.database_container = None

    def _get_database_container(self) -> Container:
        if self.database_container is None:
            self.database_container = self.docker_client.containers.list(
                all=True, filters={"label": "infrahub_role=database"}
            )[0]
        return self.database_container

    def _create_helper_container(self) -> Container:
        try:
            existing_exporter_container = self.docker_client.containers.get(self.backup_helper_container_name)
            self.console.print("Existing export container found, removing")
            existing_exporter_container.stop()
            existing_exporter_container.remove()
        except docker.errors.NotFound:
            pass
        self.console.print("Starting new export container")
        database_container = self._get_database_container()
        backup_helper_container = self.docker_client.containers.run(
            volumes_from=[database_container.name],
            name=self.backup_helper_container_name,
            image=self.neo4j_docker_image,
            tty=True,
            detach=True,
            command="/bin/bash",
        )
        backup_helper_container.exec_run(["mkdir", self.container_backup_dir])
        return backup_helper_container

    @contextmanager
    def _stopped_database_container(self) -> Generator[None, None, None]:
        database_container = self._get_database_container()
        is_running = database_container.status == "running"
        if is_running:
            self.console.print("Stopping database container")
            database_container.stop()
        yield
        if is_running:
            self.console.print("[green]Restarting Infrahub database container")
            database_container.start()

    def _transfer_files_from_container(
        self, container: Container, container_directory: str, local_directory: Path
    ) -> None:
        local_directory.mkdir()
        try:
            subprocess.run(
                ["docker", "cp", f"{container.name}:{container_directory}/.", f"{local_directory}"], check=True
            )
        except subprocess.CalledProcessError as exc:
            local_directory.rmdir()
            self.console.print("[red] failed to copy export files from docker container")
            self.console.print(f"    failed command: {exc.cmd}")
            if exc.stderr or exc.output:
                self.console.print(f"    failure details: {exc.stderr or exc.output}")
            sys.exit(exc.returncode)

    def _run_export(self, backup_container: Container) -> None:
        self.console.print("Starting neo4j database export")
        export_command = ["neo4j-admin", "database", "dump", "*", f"--to-path={self.container_backup_dir}"]
        exit_code, response = backup_container.exec_run(export_command, stdout=True, stderr=True)

        if exit_code != 0:
            self.console.print("[red]neo4j export command failed")
            self.console.print(f"    export command: {' '.join(export_command)}")
            self.console.print("    response:")
            self.console.print(response.decode())
            sys.exit(exit_code)

        self.console.print("Neo4j database export complete")

    def export(self, export_directory: Path) -> None:
        backup_helper_container = self._create_helper_container()
        with self._stopped_database_container():
            self._run_export(backup_helper_container)
            self._transfer_files_from_container(backup_helper_container, self.container_backup_dir, export_directory)
        self.console.print("Removing export container")
        backup_helper_container.stop()
        backup_helper_container.remove()
        self.console.print(f"Database dump files are in {export_directory.absolute()}")
