from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    import ssl

# Shape of the "subject" entry returned by SSLContext.get_ca_certs(): a tuple of RDNs, each a tuple of
# (attribute, value) pairs. typeshed types every entry of the certificate dict with one wide union.
SubjectType = tuple[tuple[tuple[str, str], ...], ...]


def trusted_common_names(context: ssl.SSLContext) -> set[str]:
    """Return the common names of the certificate authorities the context trusts."""
    names: set[str] = set()
    for cert in context.get_ca_certs():
        subject = cast("SubjectType", cert.get("subject", ()))
        for relative_dn in subject:
            for attribute, value in relative_dn:
                if attribute == "commonName":
                    names.add(value)
    return names
