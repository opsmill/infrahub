import sys
from io import BytesIO
from pathlib import Path
from tarfile import TarFile, TarInfo, data_filter
from typing import List, Optional

import docker
from docker.models.containers import Container
from rich.console import Console


class Neo4jBackupRunner:
    container_backup_dir = "/tmp/neo4jbackup"

    def __init__(self) -> None:
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

    def _get_existing_local_backups(self, local_backup_directory: Path) -> List[Path]:
        return [backup_file for backup_file in local_backup_directory.iterdir() if backup_file.suffix == ".backup"]

    def _prepare_container_backup_dir(self) -> None:
        database_container = self._get_database_container()
        database_container.exec_run(["rm", "-rf", f"{self.container_backup_dir}"])
        database_container.exec_run(["mkdir", "-p", self.container_backup_dir])

    def _push_backups_to_container(self, container: Container, local_backup_directory: Path) -> bool:
        if not local_backup_directory.exists():
            return False
        existing_backup_paths = self._get_existing_local_backups(local_backup_directory)
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
            self.console.print("[red]neo4j export command failed")
            self.console.print(f"    export command: {' '.join(aggregate_command)}")
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
        current_backups = self._get_existing_local_backups(local_backup_directory)

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

    def export(self, backup_directory: Path) -> None:
        database_container = self._get_database_container()
        self._prepare_container_backup_dir()
        sent_files_to_container = self._push_backups_to_container(database_container, backup_directory)
        self._run_backup(do_aggregate_backup=sent_files_to_container)
        self._update_local_backups_from_container(backup_directory)
        self.console.print(f"Updated backup files are in {backup_directory.absolute()}")
