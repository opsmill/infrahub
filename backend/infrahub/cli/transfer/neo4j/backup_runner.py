import sys
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from tarfile import TarFile, TarInfo, data_filter
from typing import AsyncGenerator, Dict, Optional

import docker
from docker.models.containers import Container
from rich.console import Console

from infrahub.database import InfrahubDatabase


class Neo4jBackupRunner:
    container_backup_dir = "/tmp/neo4jbackup"

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db
        self.docker_client = docker.from_env()
        self.console = Console()
        self.database_container = None

    def _get_database_container(self) -> Container:
        if self.database_container is None:
            containers = self.docker_client.containers.list(filters={"label": "infrahub_role=database"})
            if len(containers) == 0:
                self.console.print("No running container with label infrahub_role=database")
                sys.exit(1)
            if len(containers) > 1:
                self.console.print("Multiple running containers with label infrahub_role=database, expected one")
                sys.exit(1)
            self.database_container = containers[0]
        return self.database_container

    def _prepare_container_backup_dir(self) -> None:
        database_container = self._get_database_container()
        database_container.exec_run(["rm", "-rf", f"{self.container_backup_dir}"])
        database_container.exec_run(["mkdir", "-p", self.container_backup_dir])

    def _push_backups_to_container(self, container: Container, local_backup_directory: Path) -> bool:
        if not local_backup_directory.exists():
            return False
        existing_backup_paths = self._map_backups_to_database_name(local_backup_directory).values()
        if not existing_backup_paths:
            return False

        tar_bytes = BytesIO()
        with TarFile(fileobj=tar_bytes, mode="w") as tarfile:
            for backup_path in existing_backup_paths:
                tarfile.add(backup_path, arcname=backup_path.name)
            tarfile.close()
            tar_bytes.seek(0)
            container.put_archive(path=self.container_backup_dir, data=tar_bytes)

        return True

    def _run_backup(self, do_aggregate_backup: bool = False) -> None:
        self.console.print("Starting neo4j database backup")
        database_container = self._get_database_container()
        backup_command = ["neo4j-admin", "database", "backup", "*", f"--to-path={self.container_backup_dir}"]
        exit_code, response = database_container.exec_run(backup_command, stdout=True, stderr=True)

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
        exit_code, response = database_container.exec_run(aggregate_command, stdout=True, stderr=True)

        if exit_code != 0:
            self.console.print("[red]neo4j aggregate backups command failed")
            self.console.print(f"    aggregate backups command: {' '.join(aggregate_command)}")
            self.console.print("    response:")
            self.console.print(response.decode())
            sys.exit(exit_code)
        self.console.print("Neo4j database backup aggregation complete")

    def _tar_filter(self, tarinfo: TarInfo, dest_dir: str) -> Optional[TarInfo]:
        safe_tarinfo = data_filter(tarinfo, dest_dir)
        if safe_tarinfo.isdir():
            return None
        path = Path(safe_tarinfo.path)
        if path.suffix != ".backup":
            return None
        # remove directory from path
        safe_tarinfo.name = path.name
        return safe_tarinfo

    def _update_local_backups_from_container(self, local_backup_directory: Path) -> None:
        database_container = self._get_database_container()
        current_backups = self._map_backups_to_database_name(local_backup_directory).values()

        archive_stream, _ = database_container.get_archive(self.container_backup_dir)
        full_archive = BytesIO()
        for chunk in archive_stream:
            full_archive.write(chunk)
        full_archive.seek(0)
        with TarFile.open(fileobj=full_archive, mode="r") as tarfile:
            tarfile.extractall(local_backup_directory, filter=self._tar_filter)
            tarfile.close()

        previous_dir = local_backup_directory / Path("previous")
        if not previous_dir.exists():
            previous_dir.mkdir()
        for local_backup in current_backups:
            local_backup.rename(previous_dir / local_backup.name)

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
        if database_name != "system":
            self.console.print(f"Stopping {database_name} database")
            query = f"STOP DATABASE {database_name}"
            await self.db.execute_query(query)

        yield

        if database_name != "system":
            self.console.print(f"Starting {database_name} database")
            query = f"START DATABASE {database_name}"
            await self.db.execute_query(query)

    async def _run_restore(self, database_container: Container, backup_path_map: Dict[str, Path]) -> None:
        for database_name, local_path in backup_path_map.items():
            async with self._stopped_database(database_name):
                self.console.print(f"Beginning restore for {database_name} database")

                remote_path = Path(self.container_backup_dir) / local_path.name
                restore_command = [
                    "neo4j-admin",
                    "database",
                    "restore",
                    f"--from-path={remote_path}",
                    "--overwrite-destination=true",
                    database_name,
                ]
                exit_code, response = database_container.exec_run(restore_command, stdout=True, stderr=True)

                if exit_code != 0:
                    self.console.print(f"[red]neo4j restore command failed for {database_name} database")
                    self.console.print(f"    restore command: {' '.join(restore_command)}")
                    self.console.print("    response:")
                    self.console.print(response.decode())
                    sys.exit(exit_code)

                query = f"CREATE DATABASE {database_name} IF NOT EXISTS"
                await self.db.execute_query(query)

    async def backup(self, backup_directory: Path) -> None:
        database_container = self._get_database_container()
        self._prepare_container_backup_dir()
        sent_files_to_container = self._push_backups_to_container(database_container, backup_directory)
        self._run_backup(do_aggregate_backup=sent_files_to_container)
        self._update_local_backups_from_container(backup_directory)
        self.console.print(f"Updated backup files are in {backup_directory.absolute()}")

    async def restore(self, backup_directory: Path) -> None:
        backup_paths_by_database_name = self._map_backups_to_database_name(backup_directory)
        if not backup_paths_by_database_name:
            self.console.print(f"[red]No .backup files in {backup_directory} to use for restore")
            sys.exit(1)
        database_container = self._get_database_container()
        self._prepare_container_backup_dir()
        self._push_backups_to_container(database_container, backup_directory)
        await self._run_restore(database_container, backup_paths_by_database_name)
