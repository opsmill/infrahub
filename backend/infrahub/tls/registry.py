from __future__ import annotations

import ssl

from infrahub.tls.context_builder import TlsContextBuilder


class TlsContextRegistry:
    """Builds and caches SSL contexts by configuration parameters."""

    def __init__(self) -> None:
        self._cache: dict[tuple[bool, str | None, bool], ssl.SSLContext] = {}

    def get(self, insecure: bool = False, ca_bundle: str | None = None, force_verify: bool = False) -> ssl.SSLContext:
        """Return a cached SSL context, building it on first access."""
        key = (insecure, ca_bundle, force_verify)
        if key not in self._cache:
            self._cache[key] = TlsContextBuilder.build(
                insecure=insecure, ca_bundle=ca_bundle, force_verify=force_verify
            )
        return self._cache[key]

    def validate(self, insecure: bool = False, ca_bundle: str | None = None) -> None:
        """Build and cache the SSL context for the given config, raising ValueError on failure.

        Raises:
            ValueError: When the configured CA bundle cannot be loaded.

        """
        try:
            self.get(insecure=insecure, ca_bundle=ca_bundle)
        except ssl.SSLError as exc:
            raise ValueError(f"Unable to load CA bundle from {ca_bundle}: {exc}") from exc
