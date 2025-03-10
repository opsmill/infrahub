from __future__ import annotations

import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from .shared import (
    AVAILABLE_SERVICES,
    BUILD_NAME,
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
    from invoke.runners import Result


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
            if service in [SERVICE_SERVER_NAME, SERVICE_WORKER_NAME]:
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


def collect_container_logs(
    context: Context,
    database: str,
    namespace: Namespace,
    service: str | None = None,
    project_name: str = None,
    log_lines: int = None,
) -> Result | None:
    """Collect all logs from specified containers."""
    if not project_name:
        projects = discover_infrahub_projects(context)
        display_infrahub_projects(projects)
        project = select_infrahub_project(projects)

        if not project:
            print("No InfraHub projects found or selected. Exiting.")
            return None

        project_name = project["name"]

    logs_cmd = f"docker compose -p {project_name} logs --tail={log_lines}"
    if service:
        logs_cmd += f" {service}"

    return execute_command(context=context, command=logs_cmd, hide=True)


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

    console = Console()
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


def collect_database_logs(
    context: Context,
    database: str,
    namespace: Namespace,
    logs_dir: str,
    include_queries: bool = False,
    project_name: str = None,
) -> None:
    """Collect logs from database container using docker cp."""
    from rich.console import Console

    console = Console()

    if not project_name:
        projects = discover_infrahub_projects(context)
        display_infrahub_projects(projects)
        project = select_infrahub_project(projects)

        if not project:
            console.print("[bold red]No InfraHub projects found or selected. Exiting.[/bold red]")
            return

        project_name = project["name"]

    db_logs_dir = Path(logs_dir) / "database"
    db_logs_dir.mkdir(parents=True, exist_ok=True)

    if include_queries:
        console.print("[bold yellow]Collecting all database logs[/bold yellow]")
        execute_command(
            context=context,
            command=f"docker compose -p {project_name} cp database:/var/lib/neo4j/logs/. {db_logs_dir}/",
        )
    else:
        for log_file in ["neo4j.log", "debug.log"]:
            console.print(f"[bold yellow]Collecting database log:[/bold yellow] {log_file}")
            execute_command(
                context=context,
                command=f"docker compose -p {project_name} cp database:/var/lib/neo4j/logs/{log_file} {db_logs_dir}/",
            )


def collect_message_queue_status(
    context: Context,
    database: str,
    namespace: Namespace,
    logs_dir: str,
    project_name: str = None,
) -> None:
    """Collect message queues status and metrics."""
    from rich.console import Console

    console = Console()
    if not project_name:
        projects = discover_infrahub_projects(context)
        display_infrahub_projects(projects)
        project = select_infrahub_project(projects)

        if not project:
            console.print("[bold red]No InfraHub projects found or selected. Exiting.[/bold red]")
            return

        project_name = project["name"]

    mq_logs_dir = Path(logs_dir) / "message-queue"
    mq_logs_dir.mkdir(parents=True, exist_ok=True)

    console.print("[bold yellow]Collecting message queues status[/bold yellow]")
    commands = [
        ("queues", "rabbitmqctl list_queues name messages consumers state memory"),
        ("exchanges", "rabbitmqctl list_exchanges name type"),
        ("bindings", "rabbitmqctl list_bindings"),
        ("connections", "rabbitmqctl list_connections"),
        ("channels", "rabbitmqctl list_channels"),
        ("overview", "rabbitmqctl status"),
        ("env", "rabbitmqctl environment"),
    ]
    for name, cmd in commands:
        result = execute_command(
            context=context, command=f"docker compose -p {project_name} exec message-queue {cmd}", hide=True
        )
        if result and result.stdout:
            log_file_path = Path(mq_logs_dir) / f"{name}.log"
            log_file_path.write_text(result.stdout, encoding="utf-8")


def collect_cache_status(
    context: Context,
    database: str,
    namespace: Namespace,
    logs_dir: str,
    project_name: str = None,
) -> None:
    """Collect cache status and metrics."""
    from rich.console import Console

    console = Console()
    if not project_name:
        projects = discover_infrahub_projects(context)
        display_infrahub_projects(projects)
        project = select_infrahub_project(projects)

        if not project:
            console.print("[bold red]No InfraHub projects found or selected. Exiting.[/bold red]")
            return

        project_name = project["name"]

    cache_logs_dir = Path(logs_dir) / "cache"
    cache_logs_dir.mkdir(parents=True, exist_ok=True)

    commands = [
        ("info", "redis-cli info all"),
        ("clients", "redis-cli client list"),
        ("stats", "redis-cli info stats"),
        ("memory", "redis-cli info memory"),
        ("cpu", "redis-cli info cpu"),
        ("config", "redis-cli config get *"),
        ("slowlog", "redis-cli slowlog get 100"),
        ("keys_stats", "redis-cli --raw dbsize"),
    ]
    console.print("[bold yellow]Collecting cache status[/bold yellow]")
    for name, cmd in commands:
        result = execute_command(
            context=context, command=f"docker compose -p {project_name} exec cache {cmd}", hide=True
        )
        if result and result.stdout:
            log_file_path = Path(cache_logs_dir) / f"{name}.log"
            log_file_path.write_text(result.stdout, encoding="utf-8")


def collect_task_worker_status(
    context: Context,
    database: str,
    namespace: Namespace,
    logs_dir: str,
    project_name: str = None,
) -> None:
    """Collect task workers status and metrics."""
    from rich.console import Console

    console = Console()
    if not project_name:
        projects = discover_infrahub_projects(context)
        display_infrahub_projects(projects)
        project = select_infrahub_project(projects)

        if not project:
            console.print("[bold red]No InfraHub projects found or selected. Exiting.[/bold red]")
            return

        project_name = project["name"]

    worker_logs_dir = Path(logs_dir) / "task-worker"
    worker_logs_dir.mkdir(parents=True, exist_ok=True)

    result = execute_command(context=context, command=f"docker compose -p {project_name} ps -a task-worker", hide=True)
    if result and result.stdout:
        containers = [line.split()[0] for line in result.stdout.split("\n")[1:] if line.strip()]
        commands = [
            ("version", "prefect version"),
            ("work_pools", "prefect work-pool ls"),
            ("work_queues", "prefect work-queue ls"),
            ("task_runs", "prefect task-run ls"),
            ("flow_runs", "prefect flow-run ls"),
            ("concurrency_limits", "prefect concurrency-limit ls"),
            ("blocks", "prefect block ls"),
        ]
        console.print(f"[bold yellow]Collecting task workers status for {len(containers)} containers[/bold yellow]")
        for container in containers:
            worker_dir = Path(worker_logs_dir) / container
            worker_dir.mkdir(parents=True, exist_ok=True)
            for name, cmd in commands:
                result = execute_command(context=context, command=f"docker exec {container} {cmd}", hide=True)
                if result and result.stdout:
                    log_file_path = Path(worker_dir) / f"{name}.log"
                    log_file_path.write_text(result.stdout, encoding="utf-8")


def collect_support_data(
    context: Context,
    database: str,
    namespace: Namespace,
    include_queries: bool = False,
    log_lines: int = None,
) -> None:
    """Collect all logs from each service and create a support archive."""
    from rich.console import Console

    console = Console()
    projects = discover_infrahub_projects(context)
    display_infrahub_projects(projects)
    project = select_infrahub_project(projects)

    if not project:
        console.print("[bold red]No InfraHub projects found or selected. Exiting.[/bold red]")
        return

    project_name = project["name"]
    available_services = project["services"]

    log_lines = 100000 if log_lines is None else log_lines
    console.print(f"[bold yellow]Collecting up to {log_lines} lines of logs per container[/bold yellow]")

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    logs_dir = Path(f"support_logs_{timestamp}")
    logs_dir.mkdir(parents=True, exist_ok=True)

    project_info_file = logs_dir / "project_info.json"
    project_info_file.write_text(json.dumps(project, indent=2), encoding="utf-8")

    for service in available_services:
        console.print(f"[bold yellow]Collecting logs for service:[/bold yellow] {service}")
        result = collect_container_logs(
            context=context,
            database=database,
            namespace=namespace,
            service=service,
            project_name=project_name,
            log_lines=log_lines,
        )
        if result and result.stdout:
            log_file_path = Path(logs_dir) / f"{service}_{timestamp}.log"
            log_file_path.write_text(result.stdout, encoding="utf-8")
        else:
            console.print(f"[red]No logs found for service {service}.[/red]")

    collect_database_logs(
        context=context,
        database=database,
        namespace=namespace,
        logs_dir=str(logs_dir),
        include_queries=include_queries,
        project_name=project_name,
    )
    collect_message_queue_status(
        context=context, database=database, namespace=namespace, logs_dir=str(logs_dir), project_name=project_name
    )
    collect_cache_status(
        context=context, database=database, namespace=namespace, logs_dir=str(logs_dir), project_name=project_name
    )
    collect_task_worker_status(
        context=context, database=database, namespace=namespace, logs_dir=str(logs_dir), project_name=project_name
    )

    console.print("[bold yellow]Collecting system metrics[/bold yellow]")
    sys_metrics = collect_system_metrics()
    metrics_file = logs_dir / f"system_metrics_{timestamp}.json"
    metrics_file.write_text(json.dumps(sys_metrics, indent=2), encoding="utf-8")
    console.print("[bold yellow]Collecting container metrics[/bold yellow]")

    stats_cmd = f"docker compose -p {project_name} stats --no-stream --no-trunc --format json"
    stats_result = execute_command(context=context, command=stats_cmd, hide=True)
    if stats_result and stats_result.stdout:
        container_metrics_file = Path(logs_dir) / f"container_metrics_{timestamp}.json"
        container_metrics_file.write_text(stats_result.stdout, encoding="utf-8")

    export_dir = Path("exports")
    export_dir.mkdir(parents=True, exist_ok=True)
    archive_base = export_dir / f"support_logs_{timestamp}"
    shutil.make_archive(base_name=str(archive_base), format="gztar", root_dir=".", base_dir=str(logs_dir))
    shutil.rmtree(logs_dir)
    archive_name = f"{archive_base}.tar.gz"
    console.print(f"[green]Archive successfully created: {archive_name}[/green]")
    console.print("You can now provide this file for support analysis.")


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
