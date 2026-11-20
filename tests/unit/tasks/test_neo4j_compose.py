import json
import os
import shlex
import shutil
import subprocess

import pytest
from invoke import Context

from tasks import shared


@pytest.mark.skipif(shutil.which("docker") is None, reason="Docker Compose is required")
@pytest.mark.parametrize("namespace", [shared.Namespace.DEFAULT, shared.Namespace.DEV])
@pytest.mark.parametrize(
    ("neo4j_image", "database_image", "expected_edition"),
    [
        (None, None, "community"),
        ("neo4j:2026.05.0-enterprise", None, "enterprise"),
        (None, "neo4j:2026.05.0-enterprise", "enterprise"),
        ("neo4j:2026.05.0-enterprise", "neo4j:2026.05.0-community", "community"),
    ],
)
def test_neo4j_compose_edition(
    monkeypatch: pytest.MonkeyPatch,
    namespace: shared.Namespace,
    neo4j_image: str | None,
    database_image: str | None,
    expected_edition: str,
) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(shared, "DATABASE_DOCKER_IMAGE", database_image)
    monkeypatch.setattr(shared, "INFRAHUB_DATABASE", "neo4j")
    if neo4j_image is not None:
        monkeypatch.setattr(shared, "NEO4J_DOCKER_IMAGE", neo4j_image)

    if namespace == shared.Namespace.DEFAULT:
        files = shared.build_compose_files_cmd("neo4j", namespace)
    else:
        files = shared.build_dev_compose_files_cmd("neo4j")
    environment = dict(item.split("=", 1) for item in shlex.split(shared.get_env_vars(Context(), namespace)))
    result = subprocess.run(
        [*shlex.split(shared.get_compose_cmd(namespace)), *shlex.split(files), "config", "--format", "json"],
        env={**os.environ, **environment},
        capture_output=True,
        text=True,
        check=True,
    )
    database = json.loads(result.stdout)["services"]["database"]
    assert database["image"] == f"neo4j:2026.05.0-{expected_edition}"
    enterprise_settings = {
        key: value
        for key, value in database["environment"].items()
        if key == "NEO4J_ACCEPT_LICENSE_AGREEMENT" or key.startswith(("NEO4J_server_backup", "NEO4J_metrics"))
    }
    if expected_edition == "community":
        assert enterprise_settings == {}
    else:
        assert enterprise_settings == {
            "NEO4J_ACCEPT_LICENSE_AGREEMENT": "yes",
            "NEO4J_server_backup_enabled": "true",
            "NEO4J_server_backup_listen__address": "0.0.0.0:6362",
            "NEO4J_metrics_prometheus_enabled": "true",
            "NEO4J_metrics_enabled": "true",
            "NEO4J_metrics_prometheus_endpoint": "0.0.0.0:2004",
        }
