# ruff: noqa: INP001
"""Standalone SpecKitty dashboard server.

No external dependencies — uses only Python stdlib (http.server).
Scans specs/ for features and dev/spec-kitty/work-packages/ for kanban data.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import mimetypes
import os
import re
import signal
import socket
import subprocess  # noqa: S404
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

DASHBOARD_DIR = Path(__file__).resolve().parent
STATIC_DIR = DASHBOARD_DIR / "static"
TEMPLATE_DIR = DASHBOARD_DIR / "templates"

# Minimum number of URL path parts for API endpoints
_MIN_PARTS_SIMPLE = 4  # e.g. /api/kanban/<feature>
_MIN_PARTS_WITH_FILE = 5  # e.g. /api/artifact/<feature>/<name>


def parse_yaml_frontmatter(filepath: Path) -> dict:
    """Parse YAML frontmatter from a markdown file (simple key: value pairs)."""
    try:
        text = filepath.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    data: dict[str, Any] = {}
    current_key: str | None = None
    current_list: list[str] | None = None

    for line in match.group(1).splitlines():
        # List continuation
        if line.startswith("  - ") and current_key and current_list is not None:
            current_list.append(line.strip("- ").strip())  # type: ignore[union-attr]
            continue

        if ":" in line and not line.startswith(" "):
            # Save previous list
            if current_key and current_list is not None:
                data[current_key] = current_list

            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            # Handle explicitly empty strings: '""' or "''"
            if val in {'""', "''"}:
                data[key] = ""
                current_key = None
                current_list = None
                continue
            val = val.strip('"').strip("'")
            if not val or val == "[]":
                current_key = key
                current_list = []
            else:
                data[key] = val
                current_key = None
                current_list = None

    if current_key and current_list is not None:
        data[current_key] = current_list

    # Extract title from heading
    title_match = re.search(r"^# (?:Work Package )?WP\d+:\s*(.+)$", text, re.MULTILINE)
    if title_match:
        data["title"] = title_match.group(1).strip()

    return data


def scan_features(project_path: Path) -> list[dict[str, Any]]:
    """Scan specs/ directory for feature directories."""
    specs_dir = project_path / "specs"
    features: list[dict[str, Any]] = []

    if not specs_dir.is_dir():
        return features

    for entry in sorted(specs_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue

        # Check for at least spec.md
        spec_file = entry / "spec.md"
        if not spec_file.exists():
            continue

        feature_id = entry.name
        feature_name = feature_id.replace("-", " ").title()

        # Detect available artifacts
        artifacts = {}
        for artifact_key, filename in [
            ("spec", "spec.md"),
            ("plan", "plan.md"),
            ("tasks", "tasks.md"),
            ("research", "research.md"),
            ("quickstart", "quickstart.md"),
            ("data_model", "data-model.md"),
        ]:
            artifacts[artifact_key] = {"exists": (entry / filename).exists()}

        artifacts["kanban"] = {"exists": False}
        artifacts["contracts"] = {"exists": (entry / "contracts").is_dir()}
        artifacts["checklists"] = {"exists": (entry / "checklists").is_dir()}
        artifacts["constitution"] = {"exists": _find_constitution(project_path) is not None}

        # Find matching WP directory
        wp_base = project_path / "dev" / "spec-kitty" / "work-packages"
        wp_dir = _find_wp_dir(wp_base, feature_id)
        kanban_stats = {"planned": 0, "doing": 0, "for_review": 0, "done": 0, "total": 0}

        if wp_dir and wp_dir.is_dir():
            artifacts["kanban"] = {"exists": True}
            for wp_file in wp_dir.glob("WP*.md"):
                fm = parse_yaml_frontmatter(wp_file)
                lane = fm.get("lane", "planned")
                if lane in kanban_stats:
                    kanban_stats[lane] += 1
                kanban_stats["total"] += 1

        # Parse meta from spec frontmatter
        meta = parse_yaml_frontmatter(spec_file)

        features.append(
            {
                "id": feature_id,
                "name": feature_name,
                "path": str(entry.relative_to(project_path)),
                "artifacts": artifacts,
                "kanban_stats": kanban_stats,
                "meta": meta,
            }
        )

    return features


def _find_wp_dir(wp_base: Path, feature_id: str) -> Path | None:
    """Find the work-packages subdirectory matching a feature id."""
    if not wp_base.is_dir():
        return None

    # Try exact match first
    exact = wp_base / feature_id
    if exact.is_dir():
        return exact

    # Extract numeric prefix from feature_id (e.g., "infp-445-webhook-headers" -> "445")
    num_match = re.search(r"(\d+)", feature_id)
    if num_match:
        num = num_match.group(1)
        for entry in wp_base.iterdir():
            if entry.is_dir() and num in entry.name:
                return entry

    return None


def scan_kanban(project_path: Path, feature_id: str) -> dict[str, list[dict]]:
    """Scan work packages for a feature and return kanban lanes."""
    lanes: dict[str, list[dict]] = {"planned": [], "doing": [], "for_review": [], "done": []}

    wp_base = project_path / "dev" / "spec-kitty" / "work-packages"
    wp_dir = _find_wp_dir(wp_base, feature_id)
    if not wp_dir or not wp_dir.is_dir():
        return lanes

    for wp_file in sorted(wp_dir.glob("WP*.md")):
        fm = parse_yaml_frontmatter(wp_file)
        lane = fm.get("lane", "planned")
        if lane not in lanes:
            lane = "planned"

        # Read full content for modal
        try:
            content = wp_file.read_text(encoding="utf-8")
            # Strip frontmatter for display
            content_match = re.match(r"^---\n.*?\n---\n?(.*)", content, re.DOTALL)
            body = content_match.group(1) if content_match else content
        except (OSError, UnicodeDecodeError):
            body = ""

        card = {
            "id": fm.get("id", wp_file.stem),
            "title": fm.get("title", wp_file.stem),
            "lane": lane,
            "agent": fm.get("agent", ""),
            "assigned_to": fm.get("assigned_to", ""),
            "acceptance_criteria": fm.get("acceptance_criteria", []),
            "prompt": body,
            "subtasks": [],
        }

        # Extract subtasks from the Tasks section
        task_matches = re.findall(r"^- \[[ x]\] (.+)$", body, re.MULTILINE)
        card["subtasks"] = task_matches

        lanes[lane].append(card)

    return lanes


def _find_constitution(project_path: Path) -> Path | None:
    """Find the project constitution file."""
    candidates = [
        project_path / ".specify" / "memory" / "constitution.md",
        project_path / "dev" / "constitution.md",
        project_path / ".kittify" / "memory" / "constitution.md",
    ]
    for path in candidates:
        try:
            resolved = path.resolve()
            if resolved.exists():
                return resolved
        except (OSError, RuntimeError):
            continue
    return None


def _resolve_git_branch(project_path: Path) -> str:
    """Return the current git branch name, or empty string on failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],  # noqa: S607
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


def _is_git_worktree(project_path: Path) -> bool:
    """Return True if project_path is inside a git worktree (not the main repo)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],  # noqa: S607
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            # .git is a file (not a directory) inside worktrees
            return (project_path / ".git").is_file()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return False


def _resolve_active_mission(constitution_path: Path | None) -> str:
    """Extract the mission name from the constitution file, or return default."""
    default = "software-dev"
    if not constitution_path:
        return default
    try:
        content = constitution_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.strip().startswith("mission:"):
                return line.split(":", 1)[1].strip() or default
    except (OSError, UnicodeDecodeError):
        pass
    return default


def _check_file_integrity(specs_dir: Path) -> dict[str, Any]:
    """Check presence of expected spec files across all feature directories."""
    expected_files = ["spec.md", "plan.md", "tasks.md"]
    integrity: dict[str, Any] = {"total_expected": 0, "total_present": 0, "total_missing": 0, "missing_files": []}
    if not specs_dir.is_dir():
        return integrity
    features = [d for d in specs_dir.iterdir() if d.is_dir()]
    integrity["total_expected"] = len(features) * len(expected_files)
    missing: list[str] = []
    present = 0
    for feat_dir in features:
        for fname in expected_files:
            if (feat_dir / fname).is_file():
                present += 1
            else:
                missing.append(f"{feat_dir.name}/{fname}")
    integrity["total_present"] = present
    integrity["total_missing"] = len(missing)
    integrity["missing_files"] = missing
    return integrity


def _build_worktree_overview(wp_base: Path) -> dict[str, Any]:
    """Summarise work-package statuses from the wp_base directory."""
    overview: dict[str, Any] = {
        "total_features": 0,
        "active_worktrees": 0,
        "merged_features": 0,
        "in_development": 0,
        "not_started": 0,
    }
    if not wp_base.is_dir():
        return overview
    wp_dirs = [d for d in wp_base.iterdir() if d.is_dir()]
    overview["total_features"] = len(wp_dirs)
    for wp_dir in wp_dirs:
        status_file = wp_dir / "status.md"
        status = ""
        if status_file.is_file():
            with contextlib.suppress(OSError, UnicodeDecodeError):
                status = status_file.read_text(encoding="utf-8").lower()
        if "merged" in status:
            overview["merged_features"] += 1
        elif "in_development" in status or "in-development" in status or "active" in status:
            overview["in_development"] += 1
            overview["active_worktrees"] += 1
        else:
            overview["not_started"] += 1
    return overview


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP handler for the SpecKitty dashboard."""

    project_dir: str = ""

    def log_message(self, format: str, *args: object) -> None:
        pass  # Suppress default logging

    def _send_json(self, status: int, data: dict | list) -> None:
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, status: int, text: str, content_type: str = "text/plain") -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_404(self) -> None:
        self.send_response(404)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/":
            self._handle_root()
        elif path == "/api/features":
            self._handle_features()
        elif path.startswith("/api/kanban/"):
            self._handle_kanban(path)
        elif path.startswith("/api/artifact/"):
            self._handle_artifact(path)
        elif path.startswith("/api/research/"):
            self._handle_research(path)
        elif path.startswith("/api/contracts/"):
            self._handle_directory_listing(path, "contracts")
        elif path.startswith("/api/checklists/"):
            self._handle_directory_listing(path, "checklists")
        elif path == "/api/constitution":
            self._handle_constitution()
        elif path == "/api/diagnostics":
            self._handle_diagnostics()
        elif path == "/api/health":
            self._send_json(200, {"status": "ok", "project_path": self.project_dir})
        elif path.startswith("/static/"):
            self._handle_static(path)
        else:
            self._send_404()

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/shutdown":
            self._send_json(200, {"status": "stopping"})

            def _stop() -> None:
                time.sleep(0.05)
                self.server.shutdown()

            threading.Thread(target=_stop, daemon=True).start()
        else:
            self._send_404()

    def _handle_root(self) -> None:
        template_path = TEMPLATE_DIR / "index.html"
        try:
            html = template_path.read_text(encoding="utf-8")
            self._send_text(200, html, "text/html")
        except FileNotFoundError:
            self._send_text(500, "Template not found")

    def _handle_features(self) -> None:
        project_path = Path(self.project_dir).resolve()
        features = scan_features(project_path)

        active_feature_id = features[0]["id"] if features else None

        response = {
            "features": features,
            "active_feature_id": active_feature_id,
            "project_path": str(project_path),
            "active_worktree": "",
            "active_mission": {
                "name": "Infrahub",
                "domain": "infrastructure",
                "version": "",
                "slug": "",
                "description": "",
                "path": "",
            },
        }
        self._send_json(200, response)

    def _handle_kanban(self, path: str) -> None:
        parts = path.split("/")
        if len(parts) < _MIN_PARTS_SIMPLE:
            self._send_404()
            return

        feature_id = urllib.parse.unquote(parts[3])
        project_path = Path(self.project_dir).resolve()
        lanes = scan_kanban(project_path, feature_id)
        self._send_json(200, {"lanes": lanes})

    def _handle_artifact(self, path: str) -> None:
        parts = path.split("/")
        if len(parts) < _MIN_PARTS_WITH_FILE:
            self._send_404()
            return

        feature_id = urllib.parse.unquote(parts[3])
        artifact_name = urllib.parse.unquote(parts[4])

        artifact_map = {
            "spec": "spec.md",
            "plan": "plan.md",
            "tasks": "tasks.md",
            "research": "research.md",
            "quickstart": "quickstart.md",
            "data-model": "data-model.md",
        }

        filename = artifact_map.get(artifact_name)
        if not filename:
            self._send_404()
            return

        project_path = Path(self.project_dir).resolve()
        artifact_path = project_path / "specs" / feature_id / filename

        if not artifact_path.exists():
            self._send_404()
            return

        try:
            content = artifact_path.read_text(encoding="utf-8")
            self._send_text(200, content)
        except (OSError, UnicodeDecodeError) as exc:
            self._send_text(500, f"Error reading {filename}: {exc}")

    def _handle_research(self, path: str) -> None:
        parts = path.split("/")
        if len(parts) < _MIN_PARTS_SIMPLE:
            self._send_404()
            return

        feature_id = urllib.parse.unquote(parts[3])
        project_path = Path(self.project_dir).resolve()
        feature_dir = project_path / "specs" / feature_id

        if len(parts) == _MIN_PARTS_SIMPLE:
            # Return research.md content + artifacts list
            response: dict[str, Any] = {"main_file": None, "artifacts": []}
            research_md = feature_dir / "research.md"
            if research_md.exists():
                try:
                    response["main_file"] = research_md.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    response["main_file"] = research_md.read_text(encoding="utf-8", errors="replace")

            research_dir = feature_dir / "research"
            if research_dir.is_dir():
                for fp in sorted(research_dir.rglob("*")):
                    if fp.is_file():
                        icon = {".csv": "📊", ".md": "📝", ".json": "📋"}.get(fp.suffix, "📄")
                        response["artifacts"].append(
                            {
                                "name": fp.name,
                                "path": str(fp.relative_to(feature_dir)),
                                "icon": icon,
                            }
                        )

            self._send_json(200, response)
            return

        if len(parts) >= _MIN_PARTS_WITH_FILE:
            file_path_str = urllib.parse.unquote(parts[4])
            artifact_file = (feature_dir / file_path_str).resolve()
            try:
                artifact_file.relative_to(feature_dir.resolve())
            except ValueError:
                self._send_404()
                return

            if artifact_file.exists() and artifact_file.is_file():
                try:
                    content = artifact_file.read_text(encoding="utf-8")
                    self._send_text(200, content)
                except (UnicodeDecodeError, OSError) as exc:
                    self._send_text(500, f"Error: {exc}")
                return

        self._send_404()

    def _handle_directory_listing(self, path: str, directory_name: str) -> None:
        parts = path.split("/")
        if len(parts) < _MIN_PARTS_SIMPLE:
            self._send_404()
            return

        feature_id = urllib.parse.unquote(parts[3])
        project_path = Path(self.project_dir).resolve()
        feature_dir = project_path / "specs" / feature_id

        if len(parts) == _MIN_PARTS_SIMPLE:
            response: dict[str, Any] = {"files": []}
            artifact_dir = feature_dir / directory_name
            if artifact_dir.is_dir():
                for fp in sorted(artifact_dir.rglob("*")):
                    if fp.is_file():
                        icon = {".md": "📝", ".json": "📋"}.get(fp.suffix, "📄")
                        response["files"].append(
                            {
                                "name": fp.name,
                                "path": str(fp.relative_to(feature_dir)),
                                "icon": icon,
                            }
                        )
            self._send_json(200, response)
            return

        if len(parts) >= _MIN_PARTS_WITH_FILE:
            file_path_str = urllib.parse.unquote(parts[4])
            artifact_file = (feature_dir / file_path_str).resolve()
            try:
                artifact_file.relative_to(feature_dir.resolve())
            except ValueError:
                self._send_404()
                return

            if artifact_file.exists() and artifact_file.is_file():
                try:
                    content = artifact_file.read_text(encoding="utf-8")
                    self._send_text(200, content)
                except (UnicodeDecodeError, OSError) as exc:
                    self._send_text(500, f"Error: {exc}")
                return

        self._send_404()

    def _handle_constitution(self) -> None:
        project_path = Path(self.project_dir).resolve()
        constitution_path = _find_constitution(project_path)
        if not constitution_path:
            self._send_404()
            return
        try:
            content = constitution_path.read_text(encoding="utf-8")
            self._send_text(200, content)
        except (OSError, UnicodeDecodeError) as exc:
            self._send_text(500, f"Error: {exc}")

    def _handle_diagnostics(self) -> None:
        project_path = Path(self.project_dir).resolve()
        specs_dir = project_path / "specs"
        wp_base = project_path / "dev" / "spec-kitty" / "work-packages"
        constitution_path = _find_constitution(project_path)

        diagnostics: dict[str, Any] = {
            "project_path": str(project_path),
            "current_working_directory": str(Path.cwd()),
            "git_branch": _resolve_git_branch(project_path),
            "in_worktree": _is_git_worktree(project_path),
            "active_mission": _resolve_active_mission(constitution_path),
            "specs_dir_exists": specs_dir.is_dir(),
            "feature_count": len(list(specs_dir.iterdir())) if specs_dir.is_dir() else 0,
            "wp_dir_exists": wp_base.is_dir(),
            "wp_branches": [d.name for d in wp_base.iterdir() if d.is_dir()] if wp_base.is_dir() else [],
            "constitution_found": constitution_path is not None,
            "file_integrity": _check_file_integrity(specs_dir),
            "worktree_overview": _build_worktree_overview(wp_base),
        }
        self._send_json(200, diagnostics)

    def _handle_static(self, path: str) -> None:
        relative_path = path[len("/static/") :]
        if not relative_path:
            self._send_404()
            return

        safe_path = (STATIC_DIR / relative_path).resolve()
        try:
            safe_path.relative_to(STATIC_DIR.resolve())
        except ValueError:
            self._send_404()
            return

        if not safe_path.is_file():
            self._send_404()
            return

        mime_type, _ = mimetypes.guess_type(safe_path.name)
        try:
            data = safe_path.read_bytes()
        except OSError:
            self._send_404()
            return

        self.send_response(200)
        self.send_header("Content-Type", mime_type or "application/octet-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def find_free_port(start: int = 5050, end: int = 5100) -> int:
    """Find a free port in the given range."""
    for port in range(start, end):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    return start


def main() -> None:
    parser = argparse.ArgumentParser(description="SpecKitty Dashboard")
    parser.add_argument("--feature", help="Feature to select by default (unused, kept for compat)")
    parser.add_argument("--port", type=int, default=0, help="Port (default: auto-detect from 5050)")
    parser.add_argument("--kill", action="store_true", help="Kill running dashboard")
    parser.add_argument("--project-dir", default=None, help="Project root directory")
    args = parser.parse_args()

    if args.kill:
        os.system("pkill -f 'dashboard/server.py'")  # noqa: S605, S607
        print("Dashboard stopped.")
        return

    # Resolve project dir: walk up from script location to find specs/
    if args.project_dir:
        project_dir = Path(args.project_dir).resolve()
    else:
        # Walk up from the dashboard script to find the repo root (.git marker)
        current = DASHBOARD_DIR
        for _ in range(10):
            if (current / ".git").exists():
                break
            current = current.parent
        project_dir = current

    DashboardHandler.project_dir = str(project_dir)

    port = args.port or find_free_port()
    server = HTTPServer(("127.0.0.1", port), DashboardHandler)

    print(f"SpecKitty Dashboard: http://localhost:{port}")
    print(f"Project: {project_dir}")
    print("Press Ctrl+C to stop.")

    def _shutdown_handler(*_: object) -> None:
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown_handler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
