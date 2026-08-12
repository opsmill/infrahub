#!/usr/bin/env python3
"""Convert docker-compose-observability.yml to a standalone file.

Replaces all bind-mounted config files and directories with Docker Compose
top-level `configs` entries that embed file content inline. Also strips
profile assignments so all services start unconditionally. The resulting
compose file has zero external file dependencies and can be distributed
as a single file (e.g. via curl).

Usage:
    python convert_compose_standalone.py [INPUT] [OUTPUT]

Defaults:
    INPUT  = docker-compose-observability.yml
    OUTPUT = docker-compose-observability-standalone.yml
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.scalarstring import LiteralScalarString


def _config_key(path: str) -> str:
    """Derive a unique config key from a host-relative path.

    './grafana/provisioning/dashboards/neo4j_monitoring.json'
      -> 'grafana_provisioning_dashboards_neo4j_monitoring_json'
    """
    return path.lstrip("./").replace("/", "_").replace(".", "_").replace("-", "_")


def _read_content(base_dir: Path, host_path: str) -> str:
    """Read a file relative to *base_dir* and return its content as a string."""
    resolved = (base_dir / host_path).resolve()
    return resolved.read_text()


def _collect_bind_mounts(service: CommentedMap) -> list[dict]:
    """Return a list of bind-mount dicts from a service's volumes list."""
    volumes = service.get("volumes", [])
    mounts: list[dict] = []
    for vol in volumes:
        if isinstance(vol, str):
            parts = vol.split(":")
            host = parts[0]
            container = parts[1] if len(parts) > 1 else host
            if host.startswith(("./", "../")):
                mounts.append({"host": host, "container": container, "index": volumes.index(vol), "style": "short"})
        elif isinstance(vol, dict) and vol.get("type") == "bind":
            source = vol["source"]
            target = vol["target"]
            if source.startswith(("./", "../")):
                mounts.append({"host": source, "container": target, "index": volumes.index(vol), "style": "long"})
    return mounts


def convert(input_path: Path, output_path: Path) -> None:  # noqa: PLR0912, PLR0914, PLR0915
    base_dir = input_path.parent.resolve()
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 200  # avoid excessive line wrapping in embedded content

    compose = yaml.load(input_path)

    # Top-level configs section (will be populated)
    top_configs: CommentedMap = CommentedMap()

    services = compose.get("services", {})
    for svc in services.values():
        # Remove profiles so all services start unconditionally
        if "profiles" in svc:
            del svc["profiles"]

        mounts = _collect_bind_mounts(svc)
        if not mounts:
            continue

        # Collect all (host_path, container_path) pairs, expanding directories
        file_mappings: list[tuple[str, str]] = []
        for mount in mounts:
            host = mount["host"]
            host_resolved = (base_dir / host).resolve()
            if host_resolved.is_dir():
                for file in sorted(host_resolved.rglob("*")):
                    if file.is_file():
                        rel_to_base = "./" + str(file.relative_to(base_dir))
                        rel_inside_dir = str(file.relative_to(host_resolved))
                        container_target = mount["container"].rstrip("/") + "/" + rel_inside_dir
                        file_mappings.append((rel_to_base, container_target))
            else:
                file_mappings.append((host, mount["container"]))

        # Build config entries and service-level configs references
        svc_configs: list[CommentedMap] = []
        for host_path, container_path in file_mappings:
            key = _config_key(host_path)
            content = _read_content(base_dir, host_path)

            # For JSON files, store as a literal block scalar of the JSON text
            if host_path.endswith(".json"):
                parsed = json.loads(content)
                content = json.dumps(parsed, indent=2) + "\n"

            # In the standalone compose, the service name is "infrahub-server" not "server"
            content = content.replace('names = ["server"]', 'names = ["infrahub-server"]')

            # Escape $ as $$ so Docker Compose doesn't interpret
            # Grafana template variables like ${datasource_prometheus} as env vars
            content = content.replace("$", "$$")

            config_entry = CommentedMap()
            config_entry["content"] = LiteralScalarString(content)
            top_configs[key] = config_entry

            ref = CommentedMap()
            ref["source"] = key
            ref["target"] = container_path
            svc_configs.append(ref)

        # Remove bind-mount volumes, keep named volumes and non-bind entries
        remaining_volumes = []
        for vol in svc.get("volumes", []):
            if isinstance(vol, str):
                parts = vol.split(":")
                host = parts[0]
                if not (host.startswith(("./", "../"))):
                    remaining_volumes.append(vol)
            elif isinstance(vol, dict):
                if vol.get("type") != "bind" or not vol.get("source", "").startswith(("./", "../")):
                    remaining_volumes.append(vol)
            else:
                remaining_volumes.append(vol)

        if remaining_volumes:
            svc["volumes"] = remaining_volumes
        else:
            del svc["volumes"]

        # Add configs to service
        svc["configs"] = svc_configs

    # Add top-level configs
    compose["configs"] = top_configs

    yaml.explicit_start = True
    with Path(output_path).open("w", encoding="utf-8") as fh:
        fh.write("# yamllint disable rule:line-length rule:indentation\n")
        yaml.dump(compose, fh)
    print(f"Wrote standalone compose file to {output_path}")
    print(f"  - Embedded {len(top_configs)} config files")
    print("  - Removed all profile assignments")
    print("  - No external file dependencies remain")


def main() -> None:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docker-compose-observability.yml")
    output_path = (
        Path(sys.argv[2])
        if len(sys.argv) > 2  # noqa: PLR2004
        else input_path.with_name(input_path.stem + "-standalone" + input_path.suffix)
    )
    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)
    convert(input_path, output_path)


if __name__ == "__main__":
    main()
