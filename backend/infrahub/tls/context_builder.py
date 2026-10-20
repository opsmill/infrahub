from __future__ import annotations

import ssl

from infrahub.tls.bundle import is_pem_text


class TlsContextBuilder:
    """Builds an SSL context from TLS configuration parameters."""

    @staticmethod
    def build(insecure: bool = False, ca_bundle: str | None = None, force_verify: bool = False) -> ssl.SSLContext:
        if insecure and not force_verify:
            return ssl._create_unverified_context()

        if not ca_bundle:
            return ssl.create_default_context()

        if is_pem_text(ca_bundle):
            context = ssl.create_default_context()
            context.load_verify_locations(cadata=ca_bundle)
        else:
            context = ssl.create_default_context(cafile=ca_bundle)

        return context
