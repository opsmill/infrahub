import os
import shutil
import time
import uuid
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

from testcontainers.compose import DockerCompose
from testcontainers.core.exceptions import ContainerIsNotRunning
from typing_extensions import Self

from infrahub_testcontainers import __version__ as infrahub_version


@dataclass
class ContainerService:
    container: str
    port: int


INFRAHUB_SERVICES: dict[str, ContainerService] = {
    "server": ContainerService(container="infrahub-server-lb", port=8000),
    "task-manager": ContainerService(container="task-manager", port=4200),
    "database": ContainerService(container="database", port=7687),
    "scraper": ContainerService(container="scraper", port=8428),
    "cadvisor": ContainerService(container="cadvisor", port=8080),
}

PROJECT_ENV_VARIABLES: dict[str, str] = {
    "NEO4J_DOCKER_IMAGE": "neo4j:5.20.0-community",
    "MESSAGE_QUEUE_DOCKER_IMAGE": "rabbitmq:3.13.7-management",
    "CACHE_DOCKER_IMAGE": "redis:7.2.4",
    "INFRAHUB_TESTING_DOCKER_IMAGE": "registry.opsmill.io/opsmill/infrahub",
    "INFRAHUB_TESTING_DOCKER_ENTRYPOINT": f"gunicorn --config backend/infrahub/serve/gunicorn_config.py -w {os.environ.get('INFRAHUB_TESTING_WEB_CONCURRENCY', 4)} --logger-class infrahub.serve.log.GunicornLogger infrahub.server:app",  # noqa: E501
    "INFRAHUB_TESTING_IMAGE_VERSION": infrahub_version,
    "INFRAHUB_TESTING_PRODUCTION": "false",
    "INFRAHUB_TESTING_DB_ADDRESS": "database",
    "INFRAHUB_TESTING_LOG_LEVEL": "INFO",
    "INFRAHUB_TESTING_GIT_REPOSITORIES_DIRECTORY": "/opt/infrahub/git",
    "INFRAHUB_TESTING_API_TOKEN": "44af444d-3b26-410d-9546-b758657e026c",
    "INFRAHUB_TESTING_INITIAL_ADMIN_TOKEN": "06438eb2-8019-4776-878c-0941b1f1d1ec",
    "INFRAHUB_TESTING_INITIAL_AGENT_TOKEN": "44af444d-3b26-410d-9546-b758657e026c",
    "INFRAHUB_TESTING_SECURITY_SECRET_KEY": "327f747f-efac-42be-9e73-999f08f86b92",
    "INFRAHUB_TESTING_ADDRESS": "http://infrahub-server-lb:8000",
    "INFRAHUB_TESTING_INTERNAL_ADDRESS": "http://infrahub-server-lb:8000",
    "INFRAHUB_TESTING_BROKER_ADDRESS": "message-queue",
    "INFRAHUB_TESTING_CACHE_ADDRESS": "cache",
    "INFRAHUB_TESTING_WORKFLOW_ADDRESS": "task-manager",
    "INFRAHUB_TESTING_WORKFLOW_DEFAULT_WORKER_TYPE": "infrahubasync",
    "INFRAHUB_TESTING_TIMEOUT": "60",
    "INFRAHUB_TESTING_PREFECT_API": "http://task-manager:4200/api",
    "INFRAHUB_TESTING_LOCAL_REMOTE_GIT_DIRECTORY": "repos",
    "INFRAHUB_TESTING_INTERNAL_REMOTE_GIT_DIRECTORY": "/remote",
    "INFRAHUB_TESTING_WEB_CONCURRENCY": "4",
    "INFRAHUB_TESTING_LOCAL_DB_BACKUP_DIRECTORY": "backups",
    "INFRAHUB_TESTING_INTERNAL_DB_BACKUP_DIRECTORY": "/backups",
    "INFRAHUB_TESTING_API_SERVER_COUNT": "2",
    "INFRAHUB_TESTING_TASK_WORKER_COUNT": "2",
    "INFRAHUB_TESTING_PREFECT_UI_ENABLED": "true",
    "INFRAHUB_TESTING_DOCKER_PULL": "true",
    "INFRAHUB_TESTING_SCHEMA_STRICT_MODE": "true",
}


@dataclass
class InfrahubDockerCompose(DockerCompose):
    project_name: str | None = None
    env_vars: dict[str, str] = field(default_factory=dict)
    deployment_type: str | None = None

    @classmethod
    def init(
        cls, directory: Path | None = None, version: str | None = None, deployment_type: str | None = None
    ) -> Self:
        if not directory:
            directory = Path.cwd()

        if not version:
            version = infrahub_version

        infrahub_image_version = os.environ.get("INFRAHUB_TESTING_IMAGE_VER", None)
        if version == "local" and infrahub_image_version:
            version = infrahub_image_version

        compose = cls(project_name=cls.generate_project_name(), context=directory, deployment_type=deployment_type)
        compose.create_docker_file(directory=directory)
        compose.create_env_file(directory=directory, version=version)

        return compose

    def get_env_var(self, key: str) -> str:
        if not self.env_vars:
            raise ValueError("env_vars hasn't been initialized yet")
        if key not in self.env_vars:
            raise ValueError(f"{key} is not set in the environment variables")
        return self.env_vars[key]

    @property
    def use_neo4j_enterprise(self) -> bool:
        return "enterprise" in self.get_env_var("NEO4J_DOCKER_IMAGE")

    @property
    def internal_backup_dir(self) -> Path:
        return Path(self.get_env_var("INFRAHUB_TESTING_INTERNAL_DB_BACKUP_DIRECTORY"))

    @property
    def external_backup_dir(self) -> Path:
        return Path(self.context) / Path(self.get_env_var("INFRAHUB_TESTING_LOCAL_DB_BACKUP_DIRECTORY"))

    @classmethod
    def generate_project_name(cls) -> str:
        project_id = str(uuid.uuid4())[:8]
        return f"infrahub-test-{project_id}"

    def create_docker_file(self, directory: Path) -> Path:
        current_directory = Path(__file__).resolve().parent
        compose_file_name = (
            "docker-compose-cluster.test.yml" if self.deployment_type == "cluster" else "docker-compose.test.yml"
        )
        compose_file = current_directory / compose_file_name

        test_compose_file = directory / "docker-compose.yml"
        test_compose_file.write_bytes(compose_file.read_bytes())

        for file in ["haproxy.cfg", "prometheus.yml"]:
            config_file = current_directory / file

            test_config_file = directory / file
            test_config_file.write_bytes(config_file.read_bytes())

        return test_compose_file

    def create_env_file(self, directory: Path, version: str) -> Path:
        env_file = directory / ".env"

        PROJECT_ENV_VARIABLES.update({"INFRAHUB_TESTING_IMAGE_VERSION": version})
        if os.environ.get("INFRAHUB_TESTING_ENTERPRISE"):
            PROJECT_ENV_VARIABLES.update(
                {
                    "INFRAHUB_TESTING_DOCKER_IMAGE": "registry.opsmill.io/opsmill/infrahub-enterprise",
                    "INFRAHUB_TESTING_DOCKER_ENTRYPOINT": f"gunicorn --config community/backend/infrahub/serve/gunicorn_config.py -w {os.environ.get('INFRAHUB_TESTING_WEB_CONCURRENCY', 4)} --logger-class infrahub.serve.log.GunicornLogger infrahub_enterprise.server:app",  # noqa: E501
                    "INFRAHUB_TESTING_WORKFLOW_DEFAULT_WORKER_TYPE": "infrahubentasync",
                    "INFRAHUB_TESTING_PREFECT_UI_ENABLED": "false",
                    "NEO4J_DOCKER_IMAGE": "neo4j:5.20.0-enterprise",
                }
            )

        with env_file.open(mode="w", encoding="utf-8") as file:
            for key, value in PROJECT_ENV_VARIABLES.items():
                env_var_value = os.environ.get(key, value)
                file.write(f"{key}={env_var_value}\n")
                self.env_vars[key] = env_var_value

        return env_file.absolute()

    def restart(self) -> None:
        """
        Restart the docker compose environment.

        TODO Would be good to contribute this upstream
        """
        cmd = self.compose_command_property[:]
        cmd += ["restart"]

        if self.services:
            cmd.extend(self.services)
        self._run_command(cmd=cmd)

    def start_container(self, service_name: str | list[str]) -> None:
        """
        Starts a specific service of the docker compose environment.

        TODO Would be good to contribute this upstream
        """
        base_cmd = self.compose_command_property or []

        # pull means running a separate command before starting
        if self.pull:
            pull_cmd = [*base_cmd, "pull"]
            if isinstance(service_name, list):
                pull_cmd.extend(service_name)
            else:
                pull_cmd.append(service_name)
            self._run_command(cmd=pull_cmd)

        up_cmd = [*base_cmd, "up"]

        if self.get_env_var("INFRAHUB_TESTING_DOCKER_PULL") == "false":
            up_cmd.extend(["--pull", "never"])

        # build means modifying the up command
        if self.wait:
            up_cmd.append("--wait")
        else:
            # we run in detached mode instead of blocking
            up_cmd.append("--detach")

        if isinstance(service_name, list):
            up_cmd.extend(service_name)
        else:
            up_cmd.append(service_name)
        self._run_command(cmd=up_cmd)

    # TODO would be good to the support for project_name upstream
    @cached_property
    def compose_command_property(self) -> list[str]:
        docker_compose_cmd = [self.docker_command_path or "docker", "compose"]
        if self.compose_file_name:
            for file in self.compose_file_name:
                docker_compose_cmd += ["-f", file]
        if self.project_name:
            docker_compose_cmd += ["--project-name", self.project_name]
        if self.env_file:
            docker_compose_cmd += ["--env-file", self.env_file]
        return docker_compose_cmd

    def get_services_port(self) -> dict[str, int]:
        return {
            service_name: int(self.get_service_port(service_name=service_data.container, port=service_data.port) or 0)
            for service_name, service_data in INFRAHUB_SERVICES.items()
        }

    def database_create_backup(self, backup_name: str = "neo4j_database.backup", dest_dir: Path | None = None) -> None:
        assert self.use_neo4j_enterprise

        self.exec_in_container(
            command=[
                "neo4j-admin",
                "database",
                "backup",
                "--compress=false",
                "--to-path",
                str(self.internal_backup_dir),
            ],
            service_name="database",
        )

        if dest_dir:
            backup_files = list(self.external_backup_dir.glob("*.backup"))
            if not backup_files:
                raise FileNotFoundError(f"No .backup files found in {self.external_backup_dir}")

            backup_file = backup_files[0]
            shutil.copy(
                backup_file,
                dest_dir / backup_name,
            )

    def database_restore_backup(self, backup_file: Path) -> None:  # noqa: PLR0915
        assert self.use_neo4j_enterprise

        shutil.copy(
            str(backup_file),
            str(self.external_backup_dir / backup_file.name),
        )
        service_name = "database"

        if self.deployment_type != "cluster":  # noqa: PLR1702
            try:
                self.get_container(service_name=service_name)
            except ContainerIsNotRunning:
                self.start_container(service_name=service_name)

            self.exec_in_container(
                command=["cypher-shell", "-u", "neo4j", "-p", "admin", "STOP DATABASE neo4j;"],
                service_name=service_name,
            )

            self.exec_in_container(
                command=[
                    "neo4j-admin",
                    "database",
                    "restore",
                    "--overwrite-destination",
                    "--from-path",
                    str(self.internal_backup_dir / backup_file.name),
                ],
                service_name=service_name,
            )

            self.exec_in_container(
                command=["chown", "-R", "neo4j:neo4j", "/data"],
                service_name=service_name,
            )

            (restore_output, _, _) = self.exec_in_container(
                command=[
                    "cypher-shell",
                    "--format",
                    "plain",
                    "-d",
                    "system",
                    "-u",
                    "neo4j",
                    "-p",
                    "admin",
                    "START DATABASE neo4j;",
                ],
                service_name=service_name,
            )

            for _ in range(3):
                (stdout, _, _) = self.exec_in_container(
                    command=[
                        "cypher-shell",
                        "--format",
                        "plain",
                        "-d",
                        "system",
                        "-u",
                        "neo4j",
                        "-p",
                        "admin",
                        "SHOW DATABASES WHERE name = 'neo4j' AND currentStatus = 'online';",
                    ],
                    service_name=service_name,
                )
                if stdout:
                    break
                time.sleep(5)
            else:
                (debug_logs, _, _) = self.exec_in_container(
                    command=["cat", "logs/debug.log"],
                    service_name=service_name,
                )
                raise Exception(f"Failed to restore database:\n{restore_output}\nDebug logs:\n{debug_logs}")

            old_services = self.services
            self.services = ["infrahub-server", "task-worker"]
            self.stop(down=False)
            try:
                self.start()
            except Exception as exc:
                stdout, stderr = self.get_logs()
                raise Exception(f"Failed to start docker compose:\nStdout:\n{stdout}\nStderr:\n{stderr}") from exc
            self.services = old_services
        else:
            print("Cluster mode detected")
            try:
                self.get_container(service_name=service_name)
                self.get_container(service_name="database-core2")
                self.get_container(service_name="database-core3")
            except ContainerIsNotRunning:
                self.start_container("database", "database-core2", "database-core3")

            # Waiting for cluster to stabilize...
            time.sleep(10)

            self.exec_in_container(
                command=["cypher-shell", "-u", "neo4j", "-p", "admin", "DROP DATABASE neo4j;"],
                service_name=service_name,
            )

            self.exec_in_container(
                command=["rm", "-rf", "/data/databases/neo4j"],
                service_name=service_name,
            )
            self.exec_in_container(
                command=["rm", "-rf", "/data/transactions/neo4j"],
                service_name=service_name,
            )

            self.exec_in_container(
                command=[
                    "neo4j-admin",
                    "database",
                    "restore",
                    "--from-path",
                    str(self.internal_backup_dir / backup_file.name),
                    "neo4j",
                ],
                service_name=service_name,
            )

            cmd = self.compose_command_property[:]
            cmd += ["restart", "database"]
            self._run_command(cmd=cmd)

            main_node = service_name
            cluster_nodes = ["database", "database-core2", "database-core3"]

            for attempt in range(3):
                try:
                    (stdout, _, _) = self.exec_in_container(
                        command=[
                            "cypher-shell",
                            "--format",
                            "plain",
                            "-d",
                            "system",
                            "-u",
                            "neo4j",
                            "-p",
                            "admin",
                            "SHOW DATABASES YIELD name, address, currentStatus WHERE name = 'system' RETURN address, currentStatus",
                        ],
                        service_name=main_node,
                    )
                except Exception:
                    time.sleep(10)
                    continue

                raw_output = stdout
                nodes_status = dict.fromkeys(cluster_nodes, False)
                online_count = 0
                total_entries = 0

                try:
                    for line_raw in stdout.splitlines():
                        line = line_raw.strip()
                        if not line or line.startswith("address"):
                            continue

                        total_entries += 1
                        if "online" in line:
                            online_count += 1
                            for node in cluster_nodes:
                                node_pattern = f'"{node}:'
                                if node_pattern in line:
                                    nodes_status[node] = True
                                    break
                    if all(nodes_status.values()) and online_count == len(cluster_nodes):
                        break
                except Exception as e:
                    print(f"Error parsing database status on attempt {attempt + 1}: {e}")

                print(f"Waiting for all nodes to be online. Current status: {nodes_status}")
                time.sleep(5)
            else:
                debug_logs = {}
                for node in cluster_nodes:
                    try:
                        (logs, _, _) = self.exec_in_container(
                            command=["cat", "logs/debug.log"],
                            service_name=node,
                        )
                        debug_logs[node] = logs
                    except Exception as e:
                        debug_logs[node] = f"Could not retrieve logs: {str(e)}"

                debug_info = f"Raw output from SHOW DATABASES command:\n{raw_output}\n\n"
                debug_info += f"Final node status: {nodes_status}\n\n"

                status_str = ", ".join(
                    [f"{node}: {'online' if status else 'offline'}" for node, status in nodes_status.items()]
                )
                logs_str = debug_info + "\n\n".join(
                    [f"--- {node} logs ---\n{logs}" for node, logs in debug_logs.items()]
                )

                raise Exception(
                    f"Failed to restore database cluster. Node status: {status_str}\nDebug logs:\n{logs_str}"
                )

            server_id = None
            try:
                stdout, _, _ = self.exec_in_container(
                    command=[
                        "cypher-shell",
                        "--format",
                        "plain",
                        "-d",
                        "system",
                        "-u",
                        "neo4j",
                        "-p",
                        "admin",
                        'SHOW SERVERS YIELD name, address WHERE address = "database:7687" RETURN name;',
                    ],
                    service_name=service_name,
                )

                lines = stdout.splitlines()
                for line_raw in lines:
                    line = line_raw.strip()
                    if not line or line == "name" or line.startswith("+"):
                        continue
                    server_id = line.strip('"')
                    break
            except Exception as e:
                print(f"Error retrieving server ID with direct query: {e}")

            if server_id:
                self.exec_in_container(
                    command=[
                        "cypher-shell",
                        "-d",
                        "system",
                        "-u",
                        "neo4j",
                        "-p",
                        "admin",
                        f"CREATE DATABASE neo4j TOPOLOGY 3 PRIMARIES OPTIONS {{ existingData: 'use', existingDataSeedInstance: '{server_id}' }};",
                    ],
                    service_name=service_name,
                )
            self.start()
            print("Database restored successfully")
