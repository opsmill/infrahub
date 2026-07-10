from __future__ import annotations

import contextlib
import ssl
from typing import TYPE_CHECKING

import nats
import nats.js.api
import nats.js.errors

from infrahub import config
from infrahub.services.adapters.cache import InfrahubCache

if TYPE_CHECKING:
    from infrahub.message_bus.types import KVTTL


class NATSCache(InfrahubCache):
    connection: nats.NATS
    jetstream: nats.js.JetStreamContext
    kv: nats.js.kv.KeyValue
    bucket: str

    def __init__(
        self,
        connection: nats.NATS,
        jetstream: nats.js.JetStreamContext,
        kv: nats.js.kv.KeyValue,
        bucket: str,
    ) -> None:
        self.connection = connection
        self.jetstream = jetstream
        self.kv = kv
        self.bucket = bucket

    @classmethod
    async def new(cls) -> NATSCache:
        tls_context = None
        if config.SETTINGS.cache.tls_enabled:
            tls_context = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
            if config.SETTINGS.cache.tls_ca_file:
                tls_context.load_verify_locations(cafile=config.SETTINGS.cache.tls_ca_file)
            if config.SETTINGS.cache.tls_insecure:
                tls_context.check_hostname = False
                tls_context.verify_mode = ssl.CERT_NONE

        connection = await nats.connect(
            f"nats://{config.SETTINGS.cache.address}:{config.SETTINGS.cache.service_port}",
            user=config.SETTINGS.cache.username,
            password=config.SETTINGS.cache.password,
            tls=tls_context,
        )
        jetstream = connection.jetstream()

        bucket = f"kv_{config.SETTINGS.cache.database}"
        kv = await cls._ensure_kv(jetstream=jetstream, bucket=bucket)

        return cls(connection=connection, jetstream=jetstream, kv=kv, bucket=bucket)

    @staticmethod
    async def _ensure_kv(jetstream: nats.js.JetStreamContext, bucket: str) -> nats.js.kv.KeyValue:
        """Return the KV bucket, ensuring per-message TTL is enabled on it.

        Per-message TTL (NATS server 2.11+) lets each key carry its own expiry, replacing the
        previous approach of routing keys to separate buckets configured with a fixed bucket-wide TTL.
        """
        try:
            return await jetstream.create_key_value(config=nats.js.api.KeyValueConfig(bucket=bucket))
        except nats.js.errors.BadRequestError:
            # A bucket created by a release without per-message TTL already exists; enable it in place.
            stream = await jetstream.stream_info(f"KV_{bucket}")
            stream.config.allow_msg_ttl = True
            await jetstream.update_stream(config=stream.config)
            return await jetstream.key_value(bucket)

    @staticmethod
    def _tokenize_key_name(key: str) -> str:
        return key.replace(":", ".")

    async def delete(self, key: str) -> None:
        key = self._tokenize_key_name(key)
        with contextlib.suppress(nats.js.errors.KeyNotFoundError):
            await self.kv.delete(key)

    async def get(self, key: str) -> str | None:
        key = self._tokenize_key_name(key)
        try:
            entry = await self.kv.get(key=key)
            if entry.value:
                return entry.value.decode()
        except nats.js.errors.KeyNotFoundError:
            pass
        return None

    async def get_values(self, keys: list[str]) -> list[str | None]:
        return [await self.get(key) for key in keys]

    async def _keys(self, filter_pattern: str) -> list[str]:
        # code borrowed from py-nats keys()
        watcher = await self.kv.watch(
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

        return keys

    async def list_keys(self, filter_pattern: str) -> list[str]:
        filter_pattern = self._tokenize_key_name(filter_pattern)
        filter_pattern = filter_pattern.replace("*", ">")  # NATS uses * as token wildcard and > as full wildcard
        keys = await self._keys(filter_pattern)
        return [key.replace(".", ":") for key in keys]

    async def set(
        self, key: str, value: str, expires: KVTTL | int | None = None, not_exists: bool = False
    ) -> bool | None:
        key = self._tokenize_key_name(key)
        msg_ttl = float(expires) if expires else None
        if not_exists:
            try:
                await self.kv.create(key=key, value=value.encode(), msg_ttl=msg_ttl)
                return True
            except nats.js.errors.KeyWrongLastSequenceError:
                return False
        if msg_ttl is None:
            await self.kv.put(key=key, value=value.encode())
        else:
            # KeyValue.put() does not support per-message TTL; publish to the bucket subject directly.
            await self.jetstream.publish(f"$KV.{self.bucket}.{key}", value.encode(), msg_ttl=msg_ttl)
        return True

    async def close_connection(self) -> None: ...
