from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Union

from infrahub.core import registry
from infrahub.core.ipam.utilization import PrefixUtilizationGetter

from .base import ResourceManagerBase

if TYPE_CHECKING:
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase


class IPResourceManagerBase(ResourceManagerBase):  # pylint: disable=abstract-method
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._utilization_getter: Optional[PrefixUtilizationGetter] = None

    async def _get_utilization_getter(
        self, db: InfrahubDatabase, at: Optional[Union[Timestamp, str]] = None
    ) -> PrefixUtilizationGetter:
        if not self._utilization_getter:
            prefixes = await self.resources.get_peers(db=db, branch_agnostic=True)  # type: ignore[attr-defined]
            self._utilization_getter = PrefixUtilizationGetter(db=db, ip_prefixes=prefixes, at=at)
        return self._utilization_getter

    async def get_utilization(self, db: InfrahubDatabase, at: Optional[Union[Timestamp, str]] = None) -> float:
        utilization_getter = await self._get_utilization_getter(db=db, at=at)
        return await utilization_getter.get_use_percentage()

    async def get_utilization_default_branch(
        self, db: InfrahubDatabase, at: Optional[Union[Timestamp, str]] = None
    ) -> float:
        utilization_getter = await self._get_utilization_getter(db=db, at=at)
        return await utilization_getter.get_use_percentage(branch_names=[registry.default_branch])
