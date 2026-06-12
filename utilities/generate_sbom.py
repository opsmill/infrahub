#!/usr/bin/env -S uv run python
"""Generate a Software Bill of Materials (SBOM) for the Infrahub stack.

This utility produces a human-readable Markdown SBOM by parsing the repository's
own dependency manifests. No network access is required; everything is derived
from local files:

- ``pyproject.toml``      project metadata and direct Python dependencies
- ``uv.lock``            fully resolved Python dependency tree (direct + transitive)
- ``docker-compose.yml``  infrastructure service container images
- ``**/package.json``     direct npm dependencies for frontend, docs and packages
- ``**/package-lock.json`` / ``**/pnpm-lock.yaml``  resolved npm dependency trees

All data is auto-derived from these files. License information is gathered
best-effort from locally installed package metadata (``importlib.metadata``);
packages whose metadata is unavailable are reported as "See source". No curated
descriptions, purposes, or license facts are baked in.

Examples:
    $ uv run python utilities/generate_sbom.py
    $ uv run python utilities/generate_sbom.py --output build/Infrahub-SBOM.md

"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib  # type: ignore[no-redef]

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - pyyaml is a core dependency
    yaml = None  # type: ignore[assignment]

REPO_ROOT = Path(__file__).resolve().parent.parent

# Directories that never contain first-party manifests worth scanning.
EXCLUDED_DIRS = {"node_modules", ".venv", ".git", "dist", "build", ".mypy_cache"}

PRODUCT_NAME = "Infrahub - Infrastructure Data Management Platform"
PRODUCT_SCOPE = "Full stack: Backend + Frontend + Documentation + Infrastructure Services"

# Upper bound on a free-form ``License`` metadata field before it is treated as
# full license text rather than a short identifier.
MAX_LICENSE_FIELD_LENGTH = 60


@dataclass
class Component:
    """A single software component in the SBOM.

    Attributes:
        name: Package or image name.
        version: Resolved version (may be a constraint when unresolved).
        license: Best-effort SPDX-ish license identifier or "See source".
        description: Human-readable summary of the component's purpose.

    """

    name: str
    version: str
    license: str = "See source"
    description: str = ""


@dataclass
class ServiceImage:
    """A container image referenced by a docker-compose service.

    Attributes:
        service: The compose service name (e.g. ``message-queue``).
        image: The image repository (e.g. ``redis``).
        version: The image tag (e.g. ``8.4.0``).

    """

    service: str
    image: str
    version: str


@dataclass
class NpmManifest:
    """Parsed npm manifest plus its resolved lockfile data.

    Attributes:
        title: Display title for the manifest section.
        relative_path: Repo-relative path to the ``package.json``.
        package_name: Value of the manifest ``name`` field.
        package_version: Value of the manifest ``version`` field.
        dependencies: Mapping of runtime dependency name -> version spec.
        dev_dependencies: Mapping of dev dependency name -> version spec.
        resolved: Mapping of dependency name -> resolved version from the lockfile.
        lock_count: Number of packages found in the lockfile (0 if none parsed).

    """

    title: str
    relative_path: str
    package_name: str
    package_version: str
    dependencies: dict[str, str]
    dev_dependencies: dict[str, str]
    resolved: dict[str, str] = field(default_factory=dict)
    lock_count: int = 0


def normalize_name(name: str) -> str:
    """Normalize a Python distribution name per PEP 503.

    Args:
        name: Raw distribution name.

    Returns:
        Lower-cased name with runs of ``-``, ``_`` and ``.`` collapsed to ``-``.

    """
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_pyproject(repo_root: Path) -> tuple[dict[str, str], list[str]]:
    """Parse project metadata and direct dependency names from ``pyproject.toml``.

    Args:
        repo_root: Repository root directory.

    Returns:
        A tuple of (metadata dict, list of normalized direct dependency names).

    Raises:
        FileNotFoundError: If ``pyproject.toml`` does not exist.

    """
    pyproject_path = repo_root / "pyproject.toml"
    with pyproject_path.open("rb") as handle:
        data = tomllib.load(handle)

    project = data.get("project", {})
    meta = {
        "name": project.get("name", "infrahub"),
        "version": project.get("version", "unknown"),
        "license": project.get("license", "Apache-2.0"),
        "requires_python": project.get("requires-python", "unknown"),
        "repository": project.get("urls", {}).get("Repository", "https://github.com/opsmill/infrahub"),
        "description": project.get("description", ""),
    }

    direct = [normalize_name(_requirement_name(spec)) for spec in project.get("dependencies", [])]
    return meta, direct


def _requirement_name(requirement: str) -> str:
    """Extract the bare distribution name from a PEP 508 requirement string.

    Args:
        requirement: A requirement such as ``redis[hiredis]==6.0.0`` or
            ``tomli>=1.1.0; python_version<='3.11'``.

    Returns:
        The leading distribution name, without extras, version or markers.

    """
    spec = requirement.split(";", 1)[0].strip()
    match = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)", spec)
    return match.group(1) if match else spec


def parse_uv_lock(repo_root: Path) -> dict[str, str]:
    """Parse resolved package versions from ``uv.lock``.

    Args:
        repo_root: Repository root directory.

    Returns:
        Mapping of normalized package name -> resolved version. Empty if the
        lockfile is missing.

    """
    lock_path = repo_root / "uv.lock"
    if not lock_path.exists():
        return {}

    with lock_path.open("rb") as handle:
        data = tomllib.load(handle)

    resolved: dict[str, str] = {}
    for package in data.get("package", []):
        name = package.get("name")
        if name:
            resolved[normalize_name(name)] = package.get("version", "unknown")
    return resolved


def parse_docker_compose(repo_root: Path) -> list[ServiceImage]:
    """Parse infrastructure service images from ``docker-compose.yml``.

    Args:
        repo_root: Repository root directory.

    Returns:
        List of service images in compose declaration order, one per service
        that defines an image.

    """
    compose_path = repo_root / "docker-compose.yml"
    if not compose_path.exists() or yaml is None:
        return []

    with compose_path.open(encoding="utf-8") as handle:
        compose = yaml.safe_load(handle)

    services: list[ServiceImage] = []
    for service_name, service in (compose.get("services") or {}).items():
        image = service.get("image")
        if not image:
            continue
        image_name, version = _split_image_reference(_resolve_env_defaults(image))
        services.append(ServiceImage(service=service_name, image=image_name, version=version))
    return services


def _resolve_env_defaults(value: str) -> str:
    """Substitute ``${VAR:-default}`` / ``${VAR}`` shell expansions in a string.

    Args:
        value: A docker-compose image value possibly containing env expansions.

    Returns:
        The string with each expansion replaced by its default (or empty string).

    """
    value = re.sub(r"\$\{[^}:]+:-([^}]*)\}", r"\1", value)
    value = re.sub(r"\$\{[^}]+\}", "", value)
    return value.strip()


def _split_image_reference(image: str) -> tuple[str, str]:
    """Split a Docker image reference into repository and tag.

    Args:
        image: An image reference such as ``redis:8.4.0`` or
            ``registry.example.io/org/app:1.2.3``.

    Returns:
        A tuple of (repository, tag). Tag defaults to ``latest`` when absent.

    """
    if ":" in image and "/" not in image.rsplit(":", 1)[1]:
        repository, tag = image.rsplit(":", 1)
        return repository, tag
    return image, "latest"


def parse_package_json(path: Path) -> dict:
    """Load a ``package.json`` file.

    Args:
        path: Path to the manifest.

    Returns:
        Parsed JSON content as a dict.

    """
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def parse_npm_lock(manifest_dir: Path) -> dict[str, str]:
    """Resolve package versions from a sibling npm/pnpm lockfile.

    Prefers ``package-lock.json`` (JSON, lockfileVersion 2/3); falls back to
    ``pnpm-lock.yaml`` when present.

    Args:
        manifest_dir: Directory containing the ``package.json``.

    Returns:
        Mapping of package name -> resolved version. Empty when no lockfile is
        found or parsable.

    """
    package_lock = manifest_dir / "package-lock.json"
    if package_lock.exists():
        return _parse_package_lock(package_lock)

    pnpm_lock = manifest_dir / "pnpm-lock.yaml"
    if pnpm_lock.exists() and yaml is not None:
        return _parse_pnpm_lock(pnpm_lock)

    return {}


def _parse_package_lock(path: Path) -> dict[str, str]:
    """Parse resolved versions from an npm ``package-lock.json`` (v2/v3).

    Args:
        path: Path to the lockfile.

    Returns:
        Mapping of package name -> resolved version.

    """
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)

    resolved: dict[str, str] = {}
    for key, info in (data.get("packages") or {}).items():
        if "node_modules/" not in key:
            continue
        name = key.rsplit("node_modules/", 1)[1]
        version = info.get("version")
        if name and version:
            resolved[name] = version
    return resolved


def _parse_pnpm_lock(path: Path) -> dict[str, str]:
    """Parse resolved versions from a ``pnpm-lock.yaml`` file.

    Args:
        path: Path to the lockfile.

    Returns:
        Mapping of package name -> resolved version.

    """
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    resolved: dict[str, str] = {}
    for key in data.get("packages") or {}:
        # Keys look like "@scope/name@1.2.3" or "name@1.2.3".
        stripped = key.lstrip("/")
        at_index = stripped.rfind("@")
        if at_index <= 0:
            continue
        name = stripped[:at_index]
        version = stripped[at_index + 1 :].split("(", 1)[0]
        resolved[name] = version
    return resolved


def discover_npm_manifests(repo_root: Path) -> list[NpmManifest]:
    """Find and parse every first-party ``package.json`` in the repository.

    Args:
        repo_root: Repository root directory.

    Returns:
        List of parsed npm manifests sorted by repo-relative path.

    """
    manifests: list[NpmManifest] = []
    for manifest_path in sorted(repo_root.rglob("package.json")):
        if any(part in EXCLUDED_DIRS for part in manifest_path.relative_to(repo_root).parts):
            continue

        data = parse_package_json(manifest_path)
        relative = manifest_path.relative_to(repo_root).as_posix()
        resolved = parse_npm_lock(manifest_path.parent)
        manifests.append(
            NpmManifest(
                title=_npm_section_title(relative),
                relative_path=relative,
                package_name=data.get("name", relative),
                package_version=data.get("version", "0.0.0"),
                dependencies=data.get("dependencies", {}) or {},
                dev_dependencies=data.get("devDependencies", {}) or {},
                resolved=resolved,
                lock_count=len(resolved),
            )
        )
    return manifests


def _npm_section_title(relative_path: str) -> str:
    """Derive a readable section title from a manifest's location.

    Args:
        relative_path: Repo-relative path to ``package.json``.

    Returns:
        A human-friendly title for the SBOM section.

    """
    parent = relative_path.rsplit("/package.json", 1)[0]
    mapping = {
        "frontend/app": "Frontend Application (frontend/app)",
        "docs": "Documentation (docs)",
    }
    return mapping.get(parent, parent)


def lookup_license(distribution: str) -> str:
    """Resolve a package license from local metadata, with a curated fallback.

    Args:
        distribution: Normalized distribution name.

    Returns:
        A short license identifier, or "See source" when unknown.

    """
    try:
        meta = metadata.metadata(distribution)
    except metadata.PackageNotFoundError:
        return "See source"

    expression = meta.get("License-Expression")
    if expression:
        return expression.strip()

    for classifier in meta.get_all("Classifier") or []:
        if classifier.startswith("License :: OSI Approved :: "):
            return classifier.rsplit("::", 1)[1].strip()

    license_field = (meta.get("License") or "").strip()
    if license_field and "\n" not in license_field and len(license_field) <= MAX_LICENSE_FIELD_LENGTH:
        return license_field

    return "See source"


def lookup_summary(distribution: str) -> str:
    """Resolve a package's one-line summary from local metadata.

    Args:
        distribution: Normalized distribution name.

    Returns:
        The package summary, or an empty string when unavailable.

    """
    try:
        return (metadata.metadata(distribution).get("Summary") or "").strip()
    except metadata.PackageNotFoundError:
        return ""


def build_python_components(direct: list[str], resolved: dict[str, str]) -> tuple[list[Component], list[Component]]:
    """Build the direct and the full resolved Python component lists.

    Args:
        direct: Normalized names of direct dependencies.
        resolved: Mapping of normalized name -> resolved version from ``uv.lock``.

    Returns:
        A tuple of (direct components, all resolved components), both sorted by
        name. Each component's description is the package's metadata summary.

    """
    direct_components = [
        Component(
            name=name,
            version=resolved.get(name, "unresolved"),
            license=lookup_license(name),
            description=lookup_summary(name),
        )
        for name in sorted(set(direct))
    ]
    all_components = [
        Component(name=name, version=version, license=lookup_license(name), description=lookup_summary(name))
        for name, version in sorted(resolved.items())
    ]
    return direct_components, all_components


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    """Render a GitHub-flavored Markdown table.

    Args:
        headers: Column headers.
        rows: Table rows, each a list of cell strings.

    Returns:
        The rendered table as a string, or empty string when there are no rows.

    """
    if not rows:
        return ""
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        cells = [str(cell).replace("|", "\\|") for cell in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _render_header(meta: dict[str, str], generated_at: str) -> list[str]:
    """Render the document title and metadata table.

    Args:
        meta: Project metadata.
        generated_at: Formatted UTC generation timestamp.

    Returns:
        Markdown lines for the header block.

    """
    version = meta["version"]
    rows = [
        ["Product", PRODUCT_NAME],
        ["Version", version],
        ["Repository", meta["repository"]],
        ["License", meta["license"]],
        ["SBOM Generated", generated_at],
        ["Scope", PRODUCT_SCOPE],
    ]
    return [
        "# Software Bill of Materials (SBOM)",
        "",
        f"## Infrahub v{version} - Complete Stack",
        "",
        _md_table(["Field", "Value"], rows),
        "",
        "## Executive Summary",
        "",
        "This Software Bill of Materials documents all software components across "
        "Infrahub's complete stack. The system comprises a Python backend (FastAPI), "
        "Neo4j graph database, Redis cache, RabbitMQ message queue, PostgreSQL for "
        "auxiliary storage, and a TypeScript frontend. All components and their "
        "resolved dependencies are listed below for supply chain security and "
        "compliance purposes.",
        "",
    ]


def _render_infrastructure(services: list[ServiceImage]) -> list[str]:
    """Render the infrastructure services section.

    Args:
        services: Container images parsed from docker-compose.

    Returns:
        Markdown lines for the infrastructure section.

    """
    if not services:
        return []

    rows = [[service.service, service.image, service.version] for service in services]
    return [
        "## Infrastructure Services",
        "",
        _md_table(["Service", "Container Image", "Version"], rows),
        "",
    ]


def _render_python(meta: dict[str, str], direct: list[Component]) -> list[str]:
    """Render the direct Python dependency section.

    Args:
        meta: Project metadata (used for the Python version line).
        direct: Direct dependency components sorted by name.

    Returns:
        Markdown lines for the Python dependencies section.

    """
    rows = [[c.name, c.version, c.license, c.description] for c in direct]
    return [
        "## Python Backend Dependencies",
        "",
        f"**Python Version:** {meta['requires_python']} | **Package Manager:** uv | "
        f"**Direct dependencies:** {len(direct)}",
        "",
        _md_table(["Package", "Version", "License", "Description"], rows),
        "",
    ]


def _render_npm(manifests: list[NpmManifest]) -> list[str]:
    """Render direct npm dependency sections for each manifest.

    Args:
        manifests: Parsed npm manifests.

    Returns:
        Markdown lines for the npm dependency sections.

    """
    lines = ["## Frontend & Documentation Dependencies", ""]
    for manifest in manifests:
        rows = _npm_rows(manifest)
        lines.extend(
            [
                f"### {manifest.title}",
                "",
                f"**Package:** {manifest.package_name} `{manifest.package_version}` | "
                f"**Direct dependencies:** {len(manifest.dependencies)} runtime, "
                f"{len(manifest.dev_dependencies)} dev | "
                f"**Resolved in lockfile:** {manifest.lock_count}",
                "",
                _md_table(["Package", "Spec", "Resolved", "Scope"], rows),
                "",
            ]
        )
    return lines


def _npm_rows(manifest: NpmManifest) -> list[list[str]]:
    """Build direct-dependency rows for an npm manifest.

    Args:
        manifest: Parsed npm manifest.

    Returns:
        Rows of [name, spec, resolved version, scope].

    """
    rows: list[list[str]] = []
    for name, spec in sorted(manifest.dependencies.items()):
        rows.append([name, spec, manifest.resolved.get(name, "-"), "runtime"])
    for name, spec in sorted(manifest.dev_dependencies.items()):
        rows.append([name, spec, manifest.resolved.get(name, "-"), "dev"])
    return rows


def _render_licensing(python_all: list[Component]) -> list[str]:
    """Render the license breakdown for resolved Python packages.

    The breakdown is computed entirely from locally available package metadata;
    container image licenses are intentionally omitted because they cannot be
    derived from the repository's manifests.

    Args:
        python_all: Every resolved Python component from ``uv.lock``.

    Returns:
        Markdown lines for the licensing section.

    """
    counts: dict[str, int] = {}
    for component in python_all:
        counts[component.license] = counts.get(component.license, 0) + 1

    rows = [
        [license_id, str(count)] for license_id, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return [
        "## Licensing & Compliance",
        "",
        f"License breakdown across {len(python_all)} resolved Python packages, "
        "derived from local package metadata. Packages whose metadata is "
        'unavailable are reported as "See source".',
        "",
        _md_table(["License", "Packages"], rows),
        "",
        "For container image and npm package licenses, consult the respective "
        "registries (Docker Hub, npm) and source repositories. Use a dedicated "
        "SBOM/license scanner (e.g. CycloneDX, SPDX, FOSSA) for compliance "
        "enforcement.",
        "",
    ]


def _render_appendix(python_all: list[Component], manifests: list[NpmManifest]) -> list[str]:
    """Render the full transitive dependency appendix.

    Args:
        python_all: Every resolved Python component from ``uv.lock``.
        manifests: Parsed npm manifests with resolved lockfile data.

    Returns:
        Markdown lines for the appendix.

    """
    py_rows = [[c.name, c.version, c.license] for c in python_all]
    lines = [
        "## Appendix: Full Resolved Dependency Listing",
        "",
        f"### Python — All Resolved Packages ({len(python_all)})",
        "",
        _md_table(["Package", "Version", "License"], py_rows),
        "",
    ]

    for manifest in manifests:
        if not manifest.resolved:
            continue
        npm_rows = [[name, version] for name, version in sorted(manifest.resolved.items())]
        lines.extend(
            [
                f"### npm — {manifest.title} ({len(npm_rows)})",
                "",
                _md_table(["Package", "Version"], npm_rows),
                "",
            ]
        )
    return lines


def _render_disclaimers(generated_at: str, python_count: int, service_count: int) -> list[str]:
    """Render the document information and disclaimers section.

    Args:
        generated_at: Formatted UTC generation timestamp.
        python_count: Number of resolved Python packages.
        service_count: Number of infrastructure services.

    Returns:
        Markdown lines for the disclaimers section.

    """
    return [
        "## Document Information & Disclaimers",
        "",
        "- **SBOM Format:** Human-readable Markdown",
        f"- **Generated:** {generated_at}",
        "- **Source:** pyproject.toml + uv.lock + docker-compose.yml + package.json/lockfiles",
        "- **Coverage:** Complete stack (backend, frontend, documentation, infrastructure services)",
        "",
        "### Components Included",
        "",
        f"- Infrastructure services ({service_count} containers)",
        f"- Python backend packages ({python_count} resolved)",
        "- Frontend and documentation npm packages (direct + resolved)",
        "",
        "### Limitations",
        "",
        "- Transitive dependencies of container OS base images are not enumerated.",
        "- Specific CVE/vulnerability data is not included; use external scanners "
        "(Snyk, GitHub Dependabot, `pip-audit`, `npm audit`).",
        "- Licenses are best-effort from local package metadata; verify before relying on them for compliance.",
        "- This SBOM reflects a single point-in-time snapshot.",
        "",
        "### Security Recommendations",
        "",
        "- Run regular vulnerability scanning across all dependencies.",
        "- Monitor security advisories from PyPI, npm, and Docker Hub.",
        "- Use standardized SBOM tooling (CycloneDX, SPDX) for policy enforcement.",
        "- Keep all components updated per organizational policy.",
        "",
    ]


def generate_sbom(repo_root: Path = REPO_ROOT) -> str:
    """Generate the complete SBOM as a Markdown string.

    Args:
        repo_root: Repository root directory to scan.

    Returns:
        The rendered SBOM document.

    """
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    meta, direct = parse_pyproject(repo_root)
    resolved = parse_uv_lock(repo_root)
    services = parse_docker_compose(repo_root)
    manifests = discover_npm_manifests(repo_root)
    direct_components, python_all = build_python_components(direct, resolved)

    sections: list[str] = []
    sections += _render_header(meta, generated_at)
    sections += _render_infrastructure(services)
    sections += _render_python(meta, direct_components)
    sections += _render_npm(manifests)
    sections += _render_licensing(python_all)
    sections += _render_appendix(python_all, manifests)
    sections += _render_disclaimers(generated_at, len(python_all), len(services))

    return "\n".join(sections).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list (defaults to ``sys.argv``).

    Returns:
        Parsed arguments namespace.

    """
    parser = argparse.ArgumentParser(description="Generate a Markdown SBOM for the Infrahub stack.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=REPO_ROOT / "Infrahub-SBOM.md",
        help="Output Markdown file path. Use '-' to write to stdout.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="Repository root to scan (defaults to the Infrahub repo root).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Entry point: generate the SBOM and write it to disk or stdout.

    Args:
        argv: Optional argument list (defaults to ``sys.argv``).

    """
    args = parse_args(argv)
    document = generate_sbom(repo_root=args.repo_root)

    if str(args.output) == "-":
        sys.stdout.write(document)
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(document, encoding="utf-8")
    print(f"✅ SBOM written to {args.output} ({len(document.splitlines())} lines)")


if __name__ == "__main__":
    main()
