"""Render the `infrahubctl marketplace download` + `infrahubctl schema load` snippet.

Used by `GET /api/marketplace/cli-snippet` when a user has selected items but
no writable Git repository exists (FR-030 through FR-034 in the spec).

User-controlled values (``branch_name``, ``output_dir``, ``marketplace_url``)
are shell-quoted with :func:`shlex.quote` before being pasted into the
rendered command block — the server never executes the string itself, but the
user copies it into their own shell, so an unquoted ``; rm -rf ~`` in any
of these fields would run destructively in the caller's session.
"""

from __future__ import annotations

from shlex import quote as shell_quote
from typing import cast

from .models import CliSnippetDownload, CliSnippetResponse, MarketplaceInstallItem, MarketplaceItemKind

DEFAULT_OUTPUT_DIR = "./schemas"
DEFAULT_BRANCH = "main"


def render_cli_snippet(
    items: list[MarketplaceInstallItem],
    *,
    branch_name: str = DEFAULT_BRANCH,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    marketplace_url: str | None = None,
    default_marketplace_url: str = "https://marketplace.infrahub.app",
) -> CliSnippetResponse:
    """Produce the command block shown on the Schema Marketplace page."""
    if not items:
        raise ValueError("items must not be empty")
    if len(items) > 50:
        raise ValueError("items must not exceed 50 entries")

    include_url_flag = marketplace_url and marketplace_url.rstrip("/") != default_marketplace_url.rstrip("/")
    include_output_flag = output_dir and output_dir != DEFAULT_OUTPUT_DIR

    quoted_output_dir = shell_quote(output_dir)
    quoted_branch = shell_quote(branch_name)
    quoted_marketplace_url = shell_quote(marketplace_url) if marketplace_url else None

    downloads: list[CliSnippetDownload] = []
    for item in items:
        identifier = f"{item.namespace}/{item.name}"
        if item.kind == "collection":
            parts = ["infrahubctl", "marketplace", "download", "-c", identifier]
        else:
            parts = ["infrahubctl", "marketplace", "download", identifier]
            if item.semver:
                parts.extend(["-v", item.semver])
        if include_output_flag:
            parts.extend(["-o", quoted_output_dir])
        if include_url_flag and quoted_marketplace_url is not None:
            parts.extend(["--marketplace-url", quoted_marketplace_url])
        command = " ".join(parts)
        downloads.append(
            CliSnippetDownload(
                kind=item.kind,
                namespace=item.namespace,
                name=item.name,
                semver=item.semver if item.kind == "schema" else None,
                command=command,
            )
        )

    load_parts = ["infrahubctl", "schema", "load", quoted_output_dir, "--branch", quoted_branch]
    load_command = " ".join(load_parts)

    rendered = "\n".join([d.command for d in downloads] + [load_command])
    return CliSnippetResponse(downloads=downloads, load_command=load_command, rendered=rendered)


def parse_install_item(token: str) -> MarketplaceInstallItem:
    """Parse a ``kind:namespace/name@semver`` token. ``@semver`` is optional for schemas.

    Examples:
        schema:infrahub/vlan-translation@1.0.0
        collection:infrahub/base-schemas
    """
    if ":" not in token:
        raise ValueError(f"expected kind:namespace/name[@semver], got {token!r}")
    kind_part, rest = token.split(":", 1)
    if kind_part not in {"schema", "collection"}:
        raise ValueError(f"kind must be 'schema' or 'collection', got {kind_part!r}")
    if "@" in rest:
        identifier, semver = rest.split("@", 1)
    else:
        identifier, semver = rest, None
    if "/" not in identifier:
        raise ValueError(f"expected namespace/name, got {identifier!r}")
    namespace, name = identifier.split("/", 1)
    if not namespace or not name:
        raise ValueError(f"namespace and name must both be non-empty, got {identifier!r}")
    return MarketplaceInstallItem(
        kind=cast("MarketplaceItemKind", kind_part),
        namespace=namespace,
        name=name,
        semver=semver if kind_part == "schema" else None,
    )
