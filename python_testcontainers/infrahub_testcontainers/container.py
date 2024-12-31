import os
import uuid
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Optional

from testcontainers.compose import DockerCompose
from typing_extensions import Self

from infrahub_testcontainers import __version__ as infrahub_version


@dataclass
class ContainerService:
    container: str
    port: int


INFRAHUB_SERVICES: dict[str, ContainerService] = {
    "server": ContainerService(container="infrahub-server", port=8000),
    "task-manager": ContainerService(container="task-manager", port=4200),
}

PROJECT_ENV_VARIABLES: dict[str, str] = {
    "INFRAHUB_TESTING_DOCKER_IMAGE": "registry.opsmill.io/opsmill/infrahub",
    "INFRAHUB_TESTING_IMAGE_VERSION": infrahub_version,
    "INFRAHUB_TESTING_PRODUCTION": "false",
    "INFRAHUB_TESTING_DB_ADDRESS": "database",
    "INFRAHUB_TESTING_LOG_LEVEL": "DEBUG",
    "INFRAHUB_TESTING_GIT_REPOSITORIES_DIRECTORY": "/opt/infrahub/git",
    "INFRAHUB_TESTING_API_TOKEN": "44af444d-3b26-410d-9546-b758657e026c",
    "INFRAHUB_TESTING_INITIAL_ADMIN_TOKEN": "06438eb2-8019-4776-878c-0941b1f1d1ec",
    "INFRAHUB_TESTING_INITIAL_AGENT_TOKEN": "44af444d-3b26-410d-9546-b758657e026c",
    "INFRAHUB_TESTING_SECURITY_SECRET_KEY": "327f747f-efac-42be-9e73-999f08f86b92",
    "INFRAHUB_TESTING_ADDRESS": "http://infrahub-server:8000",
    "INFRAHUB_TESTING_INTERNAL_ADDRESS": "http://infrahub-server:8000",
    "INFRAHUB_TESTING_BROKER_ADDRESS": "message-queue",
    "INFRAHUB_TESTING_CACHE_ADDRESS": "cache",
    "INFRAHUB_TESTING_WORKFLOW_ADDRESS": "task-manager",
    "INFRAHUB_TESTING_TIMEOUT": "60",
    "INFRAHUB_TESTING_PREFECT_API": "http://task-manager:4200/api",
    "INFRAHUB_TESTING_LOCAL_REMOTE_GIT_DIRECTORY": "repos",
    "INFRAHUB_TESTING_INTERNAL_REMOTE_GIT_DIRECTORY": "/remote",
    "INFRAHUB_TESTING_WEB_CONCURRENCY": "4",
}


@dataclass
class InfrahubDockerCompose(DockerCompose):
    project_name: Optional[str] = None

    @classmethod
    def init(cls, directory: Optional[Path] = None, version: Optional[str] = None) -> Self:
        if not directory:
            directory = Path.cwd()

        if not version:
            version = infrahub_version

        infrahub_image_version = os.environ.get("INFRAHUB_TESTING_IMAGE_VER", None)
        if version == "local" and infrahub_image_version:
            version = infrahub_image_version

        cls.create_docker_file(directory=directory)
        cls.create_env_file(directory=directory, version=version)

        return cls(project_name=cls.generate_project_name(), context=directory)

    @classmethod
    def generate_project_name(cls) -> str:
        project_id = str(uuid.uuid4())[:8]
        return f"infrahub-test-{project_id}"

    @classmethod
    def create_docker_file(cls, directory: Path) -> Path:
        current_directory = Path(__file__).resolve().parent
        compose_file = current_directory / "docker-compose.test.yml"

        test_compose_file = directory / "docker-compose.yml"
        test_compose_file.write_bytes(compose_file.read_bytes())

        return test_compose_file

    @classmethod
    def create_env_file(cls, directory: Path, version: str) -> Path:
        env_file = directory / ".env"

        PROJECT_ENV_VARIABLES.update({"INFRAHUB_TESTING_IMAGE_VERSION": version})

        with env_file.open(mode="w", encoding="utf-8") as file:
            for key, value in PROJECT_ENV_VARIABLES.items():
                env_var_value = os.environ.get(key, value)
                file.write(f"{key}={env_var_value}\n")
        return env_file.absolute()

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
