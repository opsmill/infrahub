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


def mask_sensitive_data(data_dict):
    """Mask sensitive data in a dictionary."""
    sensitive_keywords = ["password", "secret", "token", "key"]

    if not isinstance(data_dict, dict):
        return data_dict

    masked_dict = data_dict.copy()
    for key in masked_dict.keys():
        if any(sensitive in key.lower() for sensitive in sensitive_keywords):
            masked_dict[key] = "********"
        elif isinstance(masked_dict[key], dict):
            masked_dict[key] = mask_sensitive_data(masked_dict[key])

    return masked_dict


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

    console = Console(force_terminal=True, color_system="auto")

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

    console = Console(force_terminal=True, color_system="auto")
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

    console = Console(force_terminal=True, color_system="auto")
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

    console = Console(force_terminal=True, color_system="auto")
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
    benchmark: bool = True,
    metrics_interval: int = 30,
) -> None:
    """Collect all logs from each service and create a support archive."""
    from rich.console import Console

    console = Console(force_terminal=True, color_system="auto")
    projects = discover_infrahub_projects(context)
    display_infrahub_projects(projects)
    project = select_infrahub_project(projects)

    if metrics_interval < 1:
        metrics_interval = 1

    console.print(
        f"[yellow]Will collect metrics every {metrics_interval} seconds throughout the collection process[/yellow]"
    )

    if not project:
        console.print("[bold red]No InfraHub projects found or selected. Exiting.[/bold red]")
        return

    project_name = project["name"]
    available_services = project["services"]
    server_name = project.get("server_name", "server")

    log_lines = 100000 if log_lines is None else log_lines
    console.print(f"[bold yellow]Collecting up to {log_lines} lines of logs per container[/bold yellow]")

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    logs_dir = Path(f"support_logs_{timestamp}")
    logs_dir.mkdir(parents=True, exist_ok=True)

    metrics_collection_context = None
    if server_name in available_services:
        metrics_collection_context = collect_prometheus_metrics(
            context=context,
            project_name=project_name,
            server_name=server_name,
            output_dir=logs_dir,
            interval_seconds=metrics_interval,
        )

    if benchmark:
        console.print("[bold yellow]Running performance benchmark...[/bold yellow]")
        collect_benchmark(context=context, logs_dir=logs_dir)
    else:
        console.print("[yellow]Skipping performance benchmark (disabled)[/yellow]")

    project_info_file = logs_dir / "project_info.json"
    project_info_file.write_text(json.dumps(project, indent=2), encoding="utf-8")

    if "task-manager" in available_services:
        server_with_curl = server_name
        collect_task_manager_info(
            context=context, project_name=project_name, server_name=server_with_curl, output_dir=logs_dir
        )
    else:
        console.print("[yellow]Task manager service not found. Skipping Prefect API collection.[/yellow]")

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
    collect_server_info(context=context, project_name=project_name, logs_dir=str(logs_dir), server_name=server_name)

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

    if metrics_collection_context:
        stop_and_save_metrics(metrics_collection_context)

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


def collect_server_info(context: Context, project_name: str, server_name: str, logs_dir: Path) -> None:
    """Collect environment, version, API info, and installed packages from server."""
    from rich.console import Console
    import json
    import re

    console = Console(force_terminal=True, color_system="auto")
    server_info_dir = Path(logs_dir) / "server"
    server_info_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"[bold yellow]Collecting information from {server_name}...[/bold yellow]")

    version_cmd = f"docker compose -p {project_name} exec {server_name} infrahubctl version"
    version_result = execute_command(context=context, command=version_cmd, hide=True)
    if version_result and version_result.stdout:
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        clean_version_output = ansi_escape.sub("", version_result.stdout)

        version_data = {}
        for line in clean_version_output.strip().split("\n"):
            if ":" in line:
                key, value = [x.strip() for x in line.split(":", 1)]
                version_data[key] = value

        version_file = server_info_dir / "version_info.json"
        version_file.write_text(json.dumps(version_data, indent=2), encoding="utf-8")

        console.print(f"[green]Version information collected as JSON.[/green]")
    else:
        console.print(f"[red]Failed to collect version information.[/red]")

    console.print(f"[bold yellow]Collecting installed Python packages...[/bold yellow]")

    pip_freeze_cmd = f"docker compose -p {project_name} exec {server_name} pip freeze"
    pip_freeze_result = execute_command(context=context, command=pip_freeze_cmd, hide=True)

    if pip_freeze_result and pip_freeze_result.stdout:
        packages = {}
        for line in pip_freeze_result.stdout.strip().split("\n"):
            if "==" in line:
                name, version = line.split("==", 1)
                packages[name.strip()] = version.strip()
            elif line:
                packages[line] = ""

        pip_packages_json = server_info_dir / "pip_packages.json"
        pip_packages_json.write_text(json.dumps(packages, indent=2), encoding="utf-8")

        console.print(f"[green]Installed Python packages list collected as JSON.[/green]")
    else:
        console.print(f"[red]Failed to collect installed Python packages list.[/red]")

    env_cmd = f"docker compose -p {project_name} exec {server_name} env"
    env_result = execute_command(context=context, command=env_cmd, hide=True)
    if env_result and env_result.stdout:
        env_vars = {}
        for line in env_result.stdout.strip().split("\n"):
            if "=" in line:
                key, value = line.split("=", 1)
                env_vars[key] = value
        env_vars = mask_sensitive_data(env_vars)
        env_file = server_info_dir / "environment.json"
        env_file.write_text(json.dumps(env_vars, indent=2), encoding="utf-8")
        console.print(f"[green]Environment information collected (with sensitive data masked).[/green]")
    else:
        console.print(f"[red]Failed to collect environment information.[/red]")

    container_id_cmd = f"docker compose -p {project_name} ps -q {server_name}"
    container_id_result = execute_command(context=context, command=container_id_cmd, hide=True)

    if container_id_result and container_id_result.stdout:
        container_id = container_id_result.stdout.strip()
        api_endpoints = ["/api/info", "/api/config", "/api/schema"]

        for endpoint in api_endpoints:
            endpoint_name = endpoint.split("/")[-1]
            console.print(f"[bold yellow]Collecting {endpoint_name} API information...[/bold yellow]")

            curl_cmd = f"docker exec {container_id} curl -s http://localhost:8000{endpoint}"
            curl_result = execute_command(context=context, command=curl_cmd, hide=True)

            if curl_result and curl_result.stdout and curl_result.stdout.strip():
                try:
                    data = json.loads(curl_result.stdout)
                    if isinstance(data, dict):
                        for key in list(data.keys()):
                            if any(sensitive in key.lower() for sensitive in ["password", "secret", "token", "key"]):
                                data[key] = "********"

                    api_file = server_info_dir / f"api_{endpoint_name}.json"
                    api_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
                    console.print(f"[green]API {endpoint_name} information collected.[/green]")
                    continue
                except json.JSONDecodeError:
                    api_file = server_info_dir / f"api_{endpoint_name}.txt"
                    api_file.write_text(curl_result.stdout, encoding="utf-8")
                    console.print(f"[green]API {endpoint_name} information collected (as text).[/green]")
                    continue

            port_cmd = f"docker port {container_id} 8000"
            port_result = execute_command(context=context, command=port_cmd, hide=True)

            if port_result and port_result.stdout:
                host_port = port_result.stdout.strip().split(":")[-1]
                host_curl_cmd = f"curl -s http://localhost:{host_port}{endpoint}"
                host_curl_result = execute_command(context=context, command=host_curl_cmd, hide=True)

                if host_curl_result and host_curl_result.stdout and host_curl_result.stdout.strip():
                    try:
                        data = json.loads(host_curl_result.stdout)
                        if isinstance(data, dict):
                            data = mask_sensitive_data(data)

                        api_file = server_info_dir / f"api_{endpoint_name}.json"
                        api_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
                        console.print(f"[green]API {endpoint_name} information collected via host port.[/green]")
                    except json.JSONDecodeError:
                        api_file = server_info_dir / f"api_{endpoint_name}.txt"
                        api_file.write_text(host_curl_result.stdout, encoding="utf-8")
                        console.print(
                            f"[green]API {endpoint_name} information collected via host port (as text).[/green]"
                        )
                else:
                    console.print(f"[red]Failed to collect API {endpoint_name} information via host port.[/red]")
            else:
                console.print(f"[red]Failed to determine port mapping for API {endpoint_name} access.[/red]")
    else:
        console.print(f"[red]Failed to get container ID for {server_name}.[/red]")


def collect_benchmark(context: Context, logs_dir: Path) -> None:
    """Run performance benchmark and collect results in JSON format."""
    from rich.console import Console
    import json
    import re

    console = Console(force_terminal=True, color_system="auto")
    benchmark_cmd = "docker run --pull always --rm registry.opsmill.io/opsmill/bench"
    benchmark_result = execute_command(context=context, command=benchmark_cmd, hide=True)

    if not benchmark_result or not benchmark_result.stdout:
        console.print("[red]Failed to run benchmark.[/red]")
        return

    pattern = r"(\w+(?:\s\w+)*): (\d+)(?: MB)? - Required: (\d+)(?: MB)? : (\w+)"
    matches = re.findall(pattern, benchmark_result.stdout)

    benchmark_data = {"raw_output": benchmark_result.stdout, "results": {}}

    for match in matches:
        category, value, required, status = match
        category_key = category.lower().replace(" ", "_")

        benchmark_data["results"][category_key] = {"value": int(value), "required": int(required), "status": status}

    benchmark_file = Path(logs_dir) / "benchmark.json"
    benchmark_file.write_text(json.dumps(benchmark_data, indent=2), encoding="utf-8")

    console.print(f"[green]Benchmark results saved to {benchmark_file}[/green]")


def collect_prometheus_metrics(
    context: Context, project_name: str, server_name: str, output_dir: Path, interval_seconds: int = 30
) -> None:
    """Collect Prometheus metrics from the server at regular intervals."""
    from rich.console import Console
    import time
    from datetime import datetime
    import threading
    import queue

    console = Console(force_terminal=True, color_system="auto")
    metrics_dir = output_dir / "prometheus-metrics"
    metrics_dir.mkdir(parents=True, exist_ok=True)

    console.print(
        f"[bold yellow]Starting Prometheus metrics collection at {interval_seconds}-second intervals[/bold yellow]"
    )

    container_id_cmd = f"docker compose -p {project_name} ps -q {server_name}"
    container_id_result = execute_command(context=context, command=container_id_cmd, hide=True)

    if not container_id_result or not container_id_result.stdout:
        console.print(f"[red]Failed to get container ID for {server_name}.[/red]")
        return

    container_id = container_id_result.stdout.strip()

    metrics_queue = queue.Queue()
    exit_flag = threading.Event()

    def metrics_collector():
        sample_count = 0
        while not exit_flag.is_set():
            try:
                timestamp = datetime.now()
                formatted_time = timestamp.strftime("%Y%m%d-%H%M%S")

                metrics_cmd = f"docker exec {container_id} curl -s http://localhost:8000/metrics"
                metrics_result = execute_command(context=context, command=metrics_cmd, hide=True)

                if metrics_result and metrics_result.stdout and metrics_result.stdout.strip():
                    metrics_queue.put(
                        {
                            "timestamp": timestamp.isoformat(),
                            "formatted_time": formatted_time,
                            "metrics_text": metrics_result.stdout,
                            "sample_number": sample_count + 1,
                        }
                    )
                    sample_count += 1
                else:
                    port_cmd = f"docker port {container_id} 8000"
                    port_result = execute_command(context=context, command=port_cmd, hide=True)

                    if port_result and port_result.stdout:
                        host_port = port_result.stdout.strip().split(":")[-1]
                        host_curl_cmd = f"curl -s http://localhost:{host_port}/metrics"
                        host_metrics_result = execute_command(context=context, command=host_curl_cmd, hide=True)

                        if host_metrics_result and host_metrics_result.stdout and host_metrics_result.stdout.strip():
                            metrics_queue.put(
                                {
                                    "timestamp": timestamp.isoformat(),
                                    "formatted_time": formatted_time,
                                    "metrics_text": host_metrics_result.stdout,
                                    "sample_number": sample_count + 1,
                                }
                            )
                            sample_count += 1
                        else:
                            console.print(f"[red]Failed to collect metrics (sample {sample_count + 1})[/red]")
                    else:
                        console.print(f"[red]Failed to get port mapping for {server_name}.[/red]")
                time.sleep(interval_seconds)
            except Exception as e:
                console.print(f"[red]Error collecting metrics: {str(e)}[/red]")
                time.sleep(interval_seconds)

    metrics_thread = threading.Thread(target=metrics_collector)
    metrics_thread.daemon = True
    metrics_thread.start()

    console.print("[green]Metrics collection started in the background.[/green]")

    return {
        "metrics_queue": metrics_queue,
        "exit_flag": exit_flag,
        "metrics_thread": metrics_thread,
        "metrics_dir": metrics_dir,
        "start_time": datetime.now(),
    }


def stop_and_save_metrics(collection_context):
    """Stop the metrics collection and save all samples to files."""
    from rich.console import Console
    from datetime import datetime
    import time

    console = Console(force_terminal=True, color_system="auto")
    metrics_queue = collection_context["metrics_queue"]
    exit_flag = collection_context["exit_flag"]
    metrics_thread = collection_context["metrics_thread"]
    metrics_dir = collection_context["metrics_dir"]
    start_time = collection_context["start_time"]
    exit_flag.set()
    time.sleep(2)
    metrics_thread.join(timeout=5)
    sample_count = 0
    all_samples_meta = []

    console.print("[yellow]Saving collected metrics samples...[/yellow]")

    while not metrics_queue.empty():
        metrics_data = metrics_queue.get()
        sample_number = metrics_data["sample_number"]
        formatted_time = metrics_data["formatted_time"]
        metrics_text = metrics_data["metrics_text"]

        metrics_file = metrics_dir / f"metrics_sample_{sample_number}_{formatted_time}.txt"
        metrics_file.write_text(metrics_text, encoding="utf-8")

        all_samples_meta.append(
            {
                "sample_number": sample_number,
                "timestamp": metrics_data["timestamp"],
                "formatted_time": formatted_time,
                "file_path": str(metrics_file.relative_to(metrics_dir.parent)),
            }
        )

        sample_count += 1

    if all_samples_meta:
        index_data = {
            "total_samples": sample_count,
            "start_time": start_time.isoformat(),
            "end_time": datetime.now().isoformat(),
            "samples": sorted(all_samples_meta, key=lambda x: x["sample_number"]),
        }

        import json

        index_file = metrics_dir / "metrics_samples_index.json"
        index_file.write_text(json.dumps(index_data, indent=2), encoding="utf-8")

    console.print(f"[green]Saved {sample_count} metrics samples to {metrics_dir}[/green]")


def collect_task_manager_info(context: Context, project_name: str, server_name: str, output_dir: Path) -> None:
    """Collect detailed information from the Prefect task manager API."""
    from rich.console import Console
    import json
    from datetime import datetime, timedelta

    console = Console(force_terminal=True, color_system="auto")
    task_manager_info_dir = output_dir / "task-manager"
    task_manager_info_dir.mkdir(parents=True, exist_ok=True)

    console.print("[bold yellow]Collecting information from task-manager (Prefect server)...[/bold yellow]")

    container_id_cmd = f"docker compose -p {project_name} ps -q {server_name}"
    container_id_result = execute_command(context=context, command=container_id_cmd, hide=True)

    if not container_id_result or not container_id_result.stdout:
        console.print(f"[red]{server_name} container not found. Cannot use curl.[/red]")
        return

    server_container_id = container_id_result.stdout.strip()

    task_manager_host = "task-manager"
    task_manager_port = "4200"

    api_endpoints = [
        {"name": "events", "path": "/api/events/filter", "method": "POST", "body": {}},
        {"name": "work_pools", "path": "/api/work_pools/filter", "method": "POST", "body": {}},
        {"name": "work_queues", "path": "/api/work_queues/filter", "method": "POST", "body": {}},
        {
            "name": "flow_runs_24h",
            "path": "/api/flow_runs/filter",
            "method": "POST",
            "body": {"created_after": (datetime.now() - timedelta(days=1)).isoformat()},
        },
        {
            "name": "work_queues_24h",
            "path": "/api/work_queues/filter",
            "method": "POST",
            "body": {"created_after": (datetime.now() - timedelta(days=1)).isoformat()},
        },
        {"name": "automations", "path": "/api/automations/filter", "method": "POST", "body": {}},
    ]

    for endpoint in api_endpoints:
        name = endpoint["name"]
        path = endpoint["path"]
        method = endpoint["method"]
        body = endpoint["body"]

        console.print(f"[yellow]Collecting {name} data...[/yellow]")

        body_json = json.dumps(body)

        if method == "POST":
            escaped_body = body_json.replace('"', '\\"')
            curl_cmd = f'docker exec {server_container_id} curl -s -X POST -H "Content-Type: application/json" -d "{escaped_body}" http://{task_manager_host}:{task_manager_port}{path}'
        else:
            curl_cmd = f"docker exec {server_container_id} curl -s http://{task_manager_host}:{task_manager_port}{path}"

        result = execute_command(context=context, command=curl_cmd, hide=True)

        if result and result.stdout:
            try:
                data = json.loads(result.stdout)
                json_file = task_manager_info_dir / f"{name}.json"
                json_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
                console.print(f"[green]Successfully collected {name} data.[/green]")
            except json.JSONDecodeError:
                console.print(f"[red]Failed to parse {name} response as JSON.[/red]")
                raw_file = task_manager_info_dir / f"{name}_raw.txt"
                raw_file.write_text(result.stdout, encoding="utf-8")
                console.print(f"[yellow]Saved raw {name} response as text.[/yellow]")
        else:
            console.print(f"[red]Failed to collect {name} data.[/red]")

    service_info_cmd = f"docker compose -p {project_name} ps task-manager --format json"
    service_info_result = execute_command(context=context, command=service_info_cmd, hide=True)

    if service_info_result and service_info_result.stdout:
        try:
            service_info = json.loads(service_info_result.stdout)
            service_info_file = task_manager_info_dir / "service_info.json"
            service_info_file.write_text(json.dumps(service_info, indent=2), encoding="utf-8")
            console.print("[green]Collected task-manager service information.[/green]")
        except json.JSONDecodeError:
            console.print("[red]Failed to parse task-manager service information.[/red]")

    console.print("[green]Task manager data collection completed.[/green]")
