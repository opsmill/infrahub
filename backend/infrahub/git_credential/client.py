from infrahub_sdk import Config

from infrahub import config
from infrahub.tls.context_builder import TlsContextBuilder


def build_client_config() -> Config:
    """Build the SDK configuration the git credential commands use to reach the Infrahub API.

    Git runs these commands as its own subprocesses, so each one has to apply the HTTP TLS settings the
    task worker applies to its own client: without them an internal address served with a private CA is
    rejected. `http.tls_insecure` outranks the CA bundle here as everywhere else, so no `force_verify`.
    """
    client_config = Config(address=config.SETTINGS.main.internal_address, insert_tracker=True)
    client_config.set_ssl_context(
        context=TlsContextBuilder.build(
            insecure=config.SETTINGS.http.tls_insecure, ca_bundle=config.SETTINGS.http.tls_ca_bundle
        )
    )
    return client_config
