from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from .shared import (
    AVAILABLE_SERVICES,
    BUILD_NAME,
    SERVICE_TASK_MANAGER_NAME,
    SERVICE_SERVER_NAME,
    SERVICE_WORKER_NAME,
    Namespace,
    build_compose_files_cmd,
    execute_command,
    get_compose_cmd,
    get_env_vars,
)
from .utils import ESCAPED_REPO_PATH

if TYPE_CHECKING:
    from invoke.context import Context


def build_images(
    context: Context,
    python_ver: str,
    nocache: bool,
    database: str,
    namespace: Namespace,
    service: str | None = None,
) -> None:
    if service and service not in AVAILABLE_SERVICES:
        sys.exit(f"{service} is not a valid service ({AVAILABLE_SERVICES})")

    print("Building images")

    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"
        print(f"base_cmd={base_cmd}")
        exec_cmd = f"build --build-arg PYTHON_VER={python_ver}"
        print(f"exec_cmd={exec_cmd}")
        if nocache:
            exec_cmd += " --no-cache"

        if os.getenv("CI") is not None:
            exec_cmd += " --progress=plain"

        if service:
            exec_cmd += f" {service}"

        execute_command(context=context, command=f"{base_cmd} {exec_cmd}", print_cmd=True)


def destroy_environment(
    context: Context,
    database: str,
    namespace: Namespace,
) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        command = f"{get_env_vars(context)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME} down --remove-orphans --volumes --timeout 1"
        execute_command(context=context, command=command)


def pull_images(context: Context, database: str, namespace: Namespace) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        for service in AVAILABLE_SERVICES:
            if service in [SERVICE_SERVER_NAME, SERVICE_WORKER_NAME, SERVICE_TASK_MANAGER_NAME]:
                continue
            command = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME} pull {service}"
            execute_command(context=context, command=command)


def restart_services(context: Context, database: str, namespace: Namespace) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"

        execute_command(context=context, command=f"{base_cmd} restart {SERVICE_SERVER_NAME}")
        execute_command(context=context, command=f"{base_cmd} restart {SERVICE_WORKER_NAME}")


def show_service_status(context: Context, database: str, namespace: Namespace) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        command = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME} ps"
        execute_command(context=context, command=command)


def start_services(context: Context, database: str, namespace: Namespace, wait: bool) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        should_wait = " --wait" if wait else ""
        command = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME} up -d{should_wait}"
        execute_command(context=context, command=command)


def stop_services(context: Context, database: str, namespace: Namespace) -> None:
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        command = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME} down"
        execute_command(context=context, command=command)


def migrate_database(context: Context, database: str, namespace: Namespace) -> None:
    """Apply the latest database migrations."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"
        command = f"{base_cmd} run {SERVICE_SERVER_NAME} infrahub db migrate"
        execute_command(context=context, command=command)


def update_core_schema(context: Context, database: str, namespace: Namespace, debug: bool = False) -> None:
    """Update the core schema."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"
        command = f"{base_cmd} run {SERVICE_SERVER_NAME} infrahub db update-core-schema"
        if debug:
            command += " --debug"
        execute_command(context=context, command=command)


def upgrade_infrahub(context: Context, database: str, namespace: Namespace, rebase_branches: bool) -> None:
    """Update Infrahub to the latest version."""
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"
        command = f"{base_cmd} run {SERVICE_SERVER_NAME} infrahub upgrade"
        if rebase_branches:
            command += " --rebase-branches"
        execute_command(context=context, command=command)


def format_bytes(bytes_value: int) -> str:
    """Convert bytes to human readable format."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_value < 1024:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024
    return f"{bytes_value:.1f} PB"


def collect_system_metrics() -> dict:
    """Collect system-wide metrics."""
    # ruff: noqa
    import psutil

    return {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "cpu": {
            "percent": psutil.cpu_percent(interval=1),
            "count": psutil.cpu_count(),
            "freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else {},
        },
        "memory": psutil.virtual_memory()._asdict(),
        "disk": {
            path: psutil.disk_usage(path)._asdict()
            for path in ["/"] + [mount.mountpoint for mount in psutil.disk_partitions() if "docker" in mount.mountpoint]
        },
        "network": {
            name: {
                "bytes_sent": stats.bytes_sent,
                "bytes_recv": stats.bytes_recv,
            }
            for name, stats in psutil.net_io_counters(pernic=True).items()
        },
    }


def parse_docker_stats_line(line: str) -> tuple[str, str, str, str, str, str, str] | None:
    """Parse a line of docker stats output safely."""
    try:
        parts = line.split()
        if len(parts) < 2 or not parts[1].startswith(BUILD_NAME):
            return None

        name = parts[1].replace(f"{BUILD_NAME}-", "")
        cpu = next((part for part in parts if part.endswith("%")), "0.00%")

        mem_index = next((i for i, part in enumerate(parts) if "MiB" in part or "GiB" in part), -1)
        if mem_index != -1:
            mem_usage = f"{parts[mem_index]} / {parts[mem_index + 2]}"
            mem_percent = parts[mem_index + 3].strip("()")
        else:
            mem_usage = "0MiB / 0GiB"
            mem_percent = "0%"

        net_index = next((i for i, part in enumerate(parts) if "B" in part and i > mem_index), -1)
        if net_index != -1:
            net_io = f"{parts[net_index]} / {parts[net_index + 2]}"
        else:
            net_io = "0B / 0B"

        block_index = next((i for i, part in enumerate(parts) if "B" in part and i > net_index), -1)
        if block_index != -1:
            block_io = f"{parts[block_index]} / {parts[block_index + 2]}"
        else:
            block_io = "0B / 0B"

        pids = next((part for part in reversed(parts) if part.isdigit()), "0")

        return name, cpu, mem_usage, mem_percent, net_io, block_io, pids

    except (IndexError, ValueError):
        return None


def display_container_status(
    context: Context,
    database: str,
    namespace: Namespace,
    watch: bool = False,
    interval: int = 2,
    project_name: str = None,
) -> None:
    """Display detailed status and metrics of all services."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    import time

    console = Console(force_terminal=True, color_system="auto")
    if not project_name:
        projects = discover_infrahub_projects(context)
        display_infrahub_projects(projects)
        project = select_infrahub_project(projects)

        if not project:
            console.print("[bold red]No InfraHub projects found or selected. Exiting.[/bold red]")
            return

        project_name = project["name"]

    try:
        while True:
            if watch:
                console.clear()

            current_time = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            console.print(Panel(f"[bold]Status at:[/bold] {current_time}", expand=False, style="cyan"))

            status_result = show_service_status(
                context=context,
                database=database,
                namespace=namespace,
            )
            if status_result and status_result.stdout:
                console.print(Panel("[bold]Container Status:[/bold]", style="magenta"))
                console.print(status_result.stdout.strip())

            sys_metrics = collect_system_metrics()
            cpu_percent = sys_metrics["cpu"]["percent"]
            cpu_count = sys_metrics["cpu"]["count"]
            memory_used = format_bytes(sys_metrics["memory"]["used"])
            memory_total = format_bytes(sys_metrics["memory"]["total"])
            memory_percent = sys_metrics["memory"]["percent"]

            system_table = Table(title="System Metrics", style="green")
            system_table.add_column("Metric", justify="right", style="bold")
            system_table.add_column("Value", justify="left")
            system_table.add_row("CPU Usage", f"{cpu_percent}% (Cores: {cpu_count})")
            system_table.add_row("Memory", f"{memory_used} / {memory_total} ({memory_percent}%)")
            console.print(system_table)

            stats_cmd = f"docker compose -p {project_name} stats --no-stream"
            stats_result = execute_command(context=context, command=stats_cmd, hide=True)

            if stats_result and stats_result.stdout:
                container_table = Table(title="Container Metrics", style="blue")
                container_table.add_column("Name", style="bold cyan")
                container_table.add_column("CPU %", justify="right")
                container_table.add_column("Memory Usage", justify="right")
                container_table.add_column("Memory %", justify="right")
                container_table.add_column("Network I/O", justify="right")
                container_table.add_column("Block I/O", justify="right")
                container_table.add_column("PIDs", justify="right")
                lines = stats_result.stdout.strip().split("\n")[1:]
                for line in lines:
                    stats = parse_docker_stats_line(line)
                    if not stats:
                        continue
                    name, cpu, mem_usage, mem_percent, net_io, block_io, pids = stats
                    try:
                        cpu_value = float(cpu.rstrip("%"))
                        mem_value = float(mem_percent.rstrip("%"))
                    except ValueError:
                        cpu_value = 0.0
                        mem_value = 0.0
                    cpu_style = "red" if cpu_value > 50 else "yellow" if cpu_value > 20 else "green"
                    mem_style = "red" if mem_value > 80 else "yellow" if mem_value > 50 else "green"
                    container_table.add_row(
                        name,
                        f"[{cpu_style}]{cpu}[/{cpu_style}]",
                        mem_usage,
                        f"[{mem_style}]{mem_percent}[/{mem_style}]",
                        net_io,
                        block_io,
                        pids,
                    )
                console.print(container_table)

            if not watch:
                break

            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[bold red]Monitoring stopped.[/bold red]")


def discover_infrahub_projects(context: Context) -> Dict[str, Dict]:
    """Discover all available InfraHub docker-compose projects."""
    compose_result = execute_command(context=context, command="docker compose ls", hide=True)
    essential_services = [
        "cache",
        "database",
        "server",
        "infrahub-server",
        "task-manager",
        "task-manager-db",
        "task-worker",
    ]
    infrahub_projects = {}

    if compose_result and compose_result.stdout:
        lines = compose_result.stdout.strip().split("\n")
        if len(lines) > 1:
            for line in lines[1:]:
                parts = line.split()
                if len(parts) >= 1:
                    project_name = parts[0]
                    services_result = execute_command(
                        context=context, command=f"docker compose -p {project_name} ps --services", hide=True
                    )

                    if services_result and services_result.stdout:
                        all_services = [s.strip() for s in services_result.stdout.strip().split("\n") if s.strip()]
                        services = [s for s in all_services if s in essential_services]
                        if "server" in services or "infrahub-server" in services:
                            infrahub_projects[project_name] = {
                                "services": services,
                                "server_name": "infrahub-server" if "infrahub-server" in services else "server",
                            }

    return infrahub_projects


def display_infrahub_projects(projects: Dict[str, Dict]) -> None:
    """Display discovered InfraHub projects in a simple line format."""
    if not projects:
        print("No projects with InfraHub services found.")
        return

    print("\nInfraHub Projects:")
    for project_name, project_info in projects.items():
        services = project_info["services"]
        server_type = project_info["server_name"]

        components = []
        components.append(f"Project: {project_name}")
        if server_type:
            components.append(f"Server: {server_type}")
        if "database" in services:
            components.append("Database: ✓")
        if "cache" in services:
            components.append("Cache: ✓")
        if "task-manager" in services:
            components.append("TaskMgr: ✓")
        if "task-manager-db" in services:
            components.append("TaskDB: ✓")
        if "task-worker" in services:
            components.append("Worker: ✓")
        print(" | ".join(components))


def select_infrahub_project(projects: Dict[str, Dict]) -> Optional[Dict]:
    """Let user select a project if multiple are found."""

    if not projects:
        print("No InfraHub projects found. Exiting.")
        return None

    requested_project = os.environ.get("INFRAHUB_BUILD_NAME")
    if requested_project and requested_project in projects:
        project_info = projects[requested_project]
        print(f"Using specified project from environment: {requested_project} (with {project_info['server_name']})")
        return {"name": requested_project, **project_info}

    if len(projects) == 1:
        project_name = list(projects.keys())[0]
        project_info = projects[project_name]
        print(f"Found single InfraHub project: {project_name} (using {project_info['server_name']})")
        return {"name": project_name, **project_info}

    print("\nMultiple InfraHub projects found:")
    for i, (project_name, project_info) in enumerate(projects.items(), 1):
        server_name = project_info["server_name"]
        print(f"{i}. {project_name} (using {server_name})")

    print("\nPlease specify which project to use with the --project parameter:")
    for project_name in projects.keys():
        print(f"  --project {project_name}")

    print("\nExiting. Please run the command again with a specific project.")
    return None
