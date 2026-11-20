"""Named locks that serialize changes to the render state of an artifact and to a validator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import lock

if TYPE_CHECKING:
    from infrahub.lock import InfrahubLock


def artifact_render_lock_name(branch: str, artifact_id: str) -> str:
    return f"artifact-render:{branch}:{artifact_id}"


def validator_lock_name(validator_id: str) -> str:
    return f"validator:{validator_id}"


def artifact_render_lock(branch: str, artifact_id: str) -> InfrahubLock:
    """Return the lock held while reading, checking and writing an artifact's render request ID, deadline and status."""
    return lock.registry.get(name=artifact_render_lock_name(branch=branch, artifact_id=artifact_id))


def validator_lock(validator_id: str) -> InfrahubLock:
    """Return the lock held while recomputing a validator's state and conclusion from its stored checks."""
    return lock.registry.get(name=validator_lock_name(validator_id=validator_id))
