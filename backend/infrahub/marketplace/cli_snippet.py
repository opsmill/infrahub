"""Render the `infrahubctl marketplace download` + `infrahubctl schema load` snippet.

Used by `GET /api/marketplace/cli-snippet` when a user has selected items but
no writable Git repository exists (FR-030 through FR-034 in the spec).
"""

from __future__ import annotations

from .models import CliSnippetDownload, CliSnippetResponse, MarketplaceInstallItem

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

    downloads: list[CliSnippetDownload] = []
    for item in items:
        parts = ["infrahubctl", "marketplace", "download", f"{item.namespace}/{item.name}"]
        if item.kind == "collection":
            parts.insert(3, "-c")  # force collection path (inserted before identifier)
            parts = ["infrahubctl", "marketplace", "download", "-c", f"{item.namespace}/{item.name}"]
        elif item.semver:
            parts.extend(["-v", item.semver])
        if include_output_flag:
            parts.extend(["-o", output_dir])
        if include_url_flag:
            parts.extend(["--marketplace-url", marketplace_url])  # type: ignore[list-item]
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

    load_parts = ["infrahubctl", "schema", "load", output_dir, "--branch", branch_name]
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
        kind=kind_part,  # type: ignore[arg-type]
        namespace=namespace,
        name=name,
        semver=semver if kind_part == "schema" else None,
    )
