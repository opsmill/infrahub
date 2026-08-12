from __future__ import annotations

import ssl
from pathlib import Path


class TlsContextBuilder:
    """Builds an SSL context from TLS configuration parameters."""

    @staticmethod
    def build(insecure: bool = False, ca_bundle: str | None = None, force_verify: bool = False) -> ssl.SSLContext:
        if insecure and not force_verify:
            return ssl._create_unverified_context()

        if not ca_bundle:
            return ssl.create_default_context()

        ca_path = Path(ca_bundle)

        try:
            possibly_file = ca_path.exists()
        except OSError:
            # Raised if the filename is too long which can indicate
            # that the value is a PEM certificate in string form.
            possibly_file = False

        if possibly_file and ca_path.is_file():
            context = ssl.create_default_context(cafile=str(ca_path))
        else:
            context = ssl.create_default_context()
            context.load_verify_locations(cadata=ca_bundle)

        return context
