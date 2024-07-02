from typing import Any

from infrahub.core.diff.model.path import DiffRoot


class DiffSerializer:
    async def serialize(self, diff_root: DiffRoot) -> dict[str, Any]:  # pylint: disable=unused-argument
        return {}


class DiffSummarySerializer:
    async def serialize(self, diff_root: DiffRoot) -> dict[str, Any]:  # pylint: disable=unused-argument
        return {}
