from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from infrahub.config import SecuritySettings, StorageSettings
from infrahub.exceptions import StorageEncryptionError
from infrahub.storage_encryption.crypto import storage_key_from_settings

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SECRET_ASSIGNMENT = re.compile(r'SECURITY_SECRET_KEY"?:[ \t]*(?:\$\{INFRAHUB_SECURITY_SECRET_KEY:-)?"?([^\s"}]+)')


@dataclass
class ShippedSecretCase:
    name: str
    path: str


SHIPPED_SECRET_CASES = [
    ShippedSecretCase(name="compose_file", path="docker-compose.yml"),
    ShippedSecretCase(name="development_compose_file", path="development/docker-compose.yml"),
    ShippedSecretCase(name="kubernetes_values", path="development/k8s/infrahub-values.yaml"),
    ShippedSecretCase(name="testcontainers", path="python_testcontainers/infrahub_testcontainers/container.py"),
]


@pytest.mark.parametrize("case", SHIPPED_SECRET_CASES, ids=lambda case: case.name)
def test_secret_that_a_shipped_file_defaults_to_is_refused_for_storage_encryption(case: ShippedSecretCase) -> None:
    secrets = SECRET_ASSIGNMENT.findall((REPOSITORY_ROOT / case.path).read_text(encoding="utf-8"))

    assert secrets
    for secret in secrets:
        with pytest.raises(StorageEncryptionError, match=r"still has the value published in Infrahub's example"):
            storage_key_from_settings(
                storage=StorageSettings(encryption_enabled=True), security=SecuritySettings(secret_key=secret)
            )
