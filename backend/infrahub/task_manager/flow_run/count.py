from typing import Protocol

from prefect.client.orchestration import PrefectClient
from prefect.client.schemas.filters import FlowFilter, FlowRunFilter

from infrahub import config
from infrahub.message_bus.types import KVTTL
from infrahub.services.adapters.cache import InfrahubCache

from .cache_key import FlowRunCountCacheKeyBuilder


class FlowRunCounterProtocol(Protocol):
    async def count(
        self,
        flow_filter: FlowFilter | None = None,
        flow_run_filter: FlowRunFilter | None = None,
    ) -> int: ...


class FlowRunCounter:
    """Count flow runs matching a filter, caching results above a configurable threshold."""

    def __init__(
        self, client: PrefectClient, cache: InfrahubCache, cache_key_builder: FlowRunCountCacheKeyBuilder
    ) -> None:
        self.client = client
        self.cache = cache
        self.cache_key_builder = cache_key_builder

    async def count(
        self,
        flow_filter: FlowFilter | None = None,
        flow_run_filter: FlowRunFilter | None = None,
    ) -> int:
        body = {
            "flows": flow_filter.model_dump(mode="json") if flow_filter else None,
            "flow_runs": (flow_run_filter.model_dump(mode="json", exclude_unset=True) if flow_run_filter else None),
        }
        cache_key = self.cache_key_builder.build(body)

        cached_value_raw = await self.cache.get(key=cache_key)
        if cached_value_raw is not None:
            try:
                return int(cached_value_raw)
            except (TypeError, ValueError):
                await self.cache.delete(key=cache_key)

        response = await self.client._client.post("/flow_runs/count", json=body)
        response.raise_for_status()
        count_value = int(response.json())

        if count_value >= config.SETTINGS.workflow.flow_run_count_cache_threshold:
            await self.cache.set(key=cache_key, value=str(count_value), expires=KVTTL.ONE_MINUTE)

        return count_value
