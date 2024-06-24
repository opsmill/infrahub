from __future__ import annotations

import ssl
from typing import TYPE_CHECKING, Optional

import nats

from infrahub import config
from infrahub.message_bus.types import KVTTL
from infrahub.services.adapters.cache import InfrahubCache

if TYPE_CHECKING:
    from infrahub.services import InfrahubServices


class NATSCache(InfrahubCache):
    def __init__(self) -> None:
        self.connection: nats.NATS
        self.jetstream: nats.js.JetStreamContext
        self.kv: dict[int, nats.js.kv.KeyValue]

        # FIXME: remove once NATS supports TTL for keys (2.11)
        self.kv_buckets = {
            self._tokenize_key_name("validator_execution_id:"): KVTTL.TWO_HOURS,
            self._tokenize_key_name("workers:primary:"): KVTTL.FIFTEEN,
            self._tokenize_key_name("workers:schema_hash:branch:"): KVTTL.TWO_HOURS,
            self._tokenize_key_name("workers:active:"): KVTTL.FIFTEEN,
            self._tokenize_key_name("workers:worker:"): KVTTL.TWO_HOURS,
        }

    async def initialize(self, service: InfrahubServices) -> None:
        tls_context = None
        if config.SETTINGS.cache.tls_enabled:
            tls_context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
            if config.SETTINGS.cache.tls_ca_file:
                tls_context.load_verify_locations(cafile=config.SETTINGS.cache.tls_ca_file)
            if config.SETTINGS.cache.tls_insecure:
                tls_context.check_hostname = False
                tls_context.verify_mode = ssl.CERT_NONE

        self.connection = await nats.connect(
            f"nats://{config.SETTINGS.cache.address}:{config.SETTINGS.cache.service_port}",
            user=config.SETTINGS.cache.username,
            password=config.SETTINGS.cache.password,
            tls=tls_context,
        )

        self.jetstream = self.connection.jetstream()

        kv_config = nats.js.api.KeyValueConfig(bucket=f"kv_{config.SETTINGS.cache.database}")
        self.kv = {0: await self.jetstream.create_key_value(config=kv_config)}

        # FIXME: remove once NATS supports TTL for keys (2.11)
        for ttl in KVTTL.variations():
            kv_config.bucket = f"kv_{config.SETTINGS.cache.database}_ttl_{ttl.name.lower()}"
            kv_config.ttl = ttl.value
            self.kv[ttl.value] = await self.jetstream.create_key_value(config=kv_config)

    def _tokenize_key_name(self, key: str) -> str:
        return key.replace(":", ".")

    # FIXME: remove once NATS supports TTL for keys (2.11)
    def _get_kv(self, key: str) -> nats.js.kv.KeyValue:
        for bucket, ttl in self.kv_buckets.items():
            if key.startswith(bucket):
                return self.kv[ttl.value]
        return self.kv[0]

    async def delete(self, key: str) -> None:
        key = self._tokenize_key_name(key)
        await self._get_kv(key).delete(key)

    async def get(self, key: str) -> Optional[str]:
        key = self._tokenize_key_name(key)
        try:
            entry = await self._get_kv(key).get(key=key)
            if entry.value:
                return entry.value.decode()
        except nats.js.errors.KeyNotFoundError:
            pass
        return None

    async def get_values(self, keys: list[str]) -> list[Optional[str]]:
        return [await self.get(key) for key in keys]

    async def _keys(self, kv: nats.js.kv.KeyValue, filter_pattern: str) -> list[str]:
        # code borrowed from py-nats keys()
        watcher = await kv.watch(
            filter_pattern,
            ignore_deletes=True,
            meta_only=True,
        )
        keys = []

        async for key in watcher:
            # None entry is used to signal that there is no more info.
            if not key:
                break
            keys.append(key.key)
        await watcher.stop()

        if not keys:
            return []

        return keys

    async def list_keys(self, filter_pattern: str) -> list[str]:
        # return await self.kv[None].keys() # does not support filtering
        filter_pattern = self._tokenize_key_name(filter_pattern)
        filter_pattern = filter_pattern.replace("*", ">")  # NATS uses * as token wildcard and > as full wildcard
        # FIXME: remove once NATS supports TTL for keys (2.11)
        if filter_pattern.startswith("workers."):
            keys = await self._keys(self.kv[KVTTL.FIFTEEN.value], filter_pattern) + await self._keys(
                self.kv[KVTTL.TWO_HOURS.value], filter_pattern
            )
        elif filter_pattern.startswith("validator_execution_id."):
            keys = await self._keys(self.kv[KVTTL.TWO_HOURS.value], filter_pattern)
        else:
            keys = await self._keys(self.kv[0], filter_pattern)

        return [key.replace(".", ":") for key in keys]

    async def set(
        self, key: str, value: str, expires: Optional[KVTTL] = None, not_exists: bool = False
    ) -> Optional[bool]:
        key = self._tokenize_key_name(key)
        if not_exists:
            try:
                await self._get_kv(key).create(key=key, value=value.encode())
                return True
            except nats.js.errors.KeyWrongLastSequenceError:
                return False
        await self._get_kv(key).put(key=key, value=value.encode())
        return True
