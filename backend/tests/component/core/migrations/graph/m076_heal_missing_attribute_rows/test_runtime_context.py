import pytest

from infrahub import lock
from infrahub.core.branch import Branch
from infrahub.core.migrations.graph.missing_attribute_rows.healer import ensure_runtime_context
from infrahub.database import InfrahubDatabase
from infrahub.lock import UninitializedLockRegistry


async def test_runtime_context_initializes_an_uninitialized_lock_registry(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(lock, "registry", UninitializedLockRegistry())

    await ensure_runtime_context(db=db)

    assert lock.is_initialized()
