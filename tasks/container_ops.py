from __future__ import annotations

import json
import shutil
import sys
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
) -> Result | None:
    """Collect all logs from specified containers."""
    if service and service not in AVAILABLE_SERVICES:
        services_str = "\n- ".join([""] + AVAILABLE_SERVICES)
        raise ValueError(f"Unknown service '{service}'. Available services:{services_str}")

    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"

        logs_cmd = f"{base_cmd} logs --tail=20000"
        if service:
            logs_cmd += f" {service}"

        return execute_command(context=context, command=logs_cmd, hide=True)


def display_container_status(
    context: Context,
    database: str,
    namespace: Namespace,
    watch: bool = False,
    interval: int = 2,
) -> None:
    """Display detailed status and metrics of all services."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    import time

    console = Console()

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

            with context.cd(ESCAPED_REPO_PATH):
                compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
                compose_cmd = get_compose_cmd(namespace=namespace)
                base_cmd = (
                    f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"
                )

                stats_result = execute_command(context=context, command=f"{base_cmd} stats --no-stream", hide=True)

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
) -> None:
    """Collect logs from database container using docker cp."""
    from rich.console import Console

    console = Console()
    db_logs_dir = Path(logs_dir) / "database"
    db_logs_dir.mkdir(parents=True, exist_ok=True)

    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"

        if include_queries:
            console.print("[bold yellow]Collecting all database logs[/bold yellow]")
            execute_command(
                context=context,
                command=f"{base_cmd} cp database:/var/lib/neo4j/logs/. {db_logs_dir}/",
            )
        else:
            for log_file in ["neo4j.log", "debug.log"]:
                console.print(f"[bold yellow]Collecting database log:[/bold yellow] {log_file}")
                execute_command(
                    context=context,
                    command=f"{base_cmd} cp database:/var/lib/neo4j/logs/{log_file} {db_logs_dir}/",
                )


def collect_message_queue_status(
    context: Context,
    database: str,
    namespace: Namespace,
    logs_dir: str,
) -> None:
    """Collect message queues status and metrics."""
    from rich.console import Console

    console = Console()
    mq_logs_dir = Path(logs_dir) / "message-queue"
    mq_logs_dir.mkdir(parents=True, exist_ok=True)

    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"

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
            result = execute_command(context=context, command=f"{base_cmd} exec message-queue {cmd}", hide=True)
            if result and result.stdout:
                log_file_path = Path(mq_logs_dir) / f"{name}.log"
                log_file_path.write_text(result.stdout, encoding="utf-8")


def collect_cache_status(
    context: Context,
    database: str,
    namespace: Namespace,
    logs_dir: str,
) -> None:
    """Collect cache status and metrics."""
    from rich.console import Console

    console = Console()
    cache_logs_dir = Path(logs_dir) / "cache"
    cache_logs_dir.mkdir(parents=True, exist_ok=True)

    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"

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
            result = execute_command(context=context, command=f"{base_cmd} exec cache {cmd}", hide=True)
            if result and result.stdout:
                log_file_path = Path(cache_logs_dir) / f"{name}.log"
                log_file_path.write_text(result.stdout, encoding="utf-8")


def collect_task_worker_status(
    context: Context,
    database: str,
    namespace: Namespace,
    logs_dir: str,
) -> None:
    """Collect task workers status and metrics."""
    from rich.console import Console

    console = Console()
    worker_logs_dir = Path(logs_dir) / "task-worker"
    worker_logs_dir.mkdir(parents=True, exist_ok=True)

    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"

        result = execute_command(context=context, command=f"{base_cmd} ps -a task-worker", hide=True)

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
) -> None:
    """Collect all logs from each service and create a support archive."""
    from rich.console import Console

    console = Console()
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    logs_dir = Path(f"support_logs_{timestamp}")
    logs_dir.mkdir(parents=True, exist_ok=True)

    for service in AVAILABLE_SERVICES:
        console.print(f"[bold yellow]Collecting logs for service:[/bold yellow] {service}")
        result = collect_container_logs(
            context=context,
            database=database,
            namespace=namespace,
            service=service,
        )
        if result and result.stdout:
            log_file_path = Path(logs_dir) / f"{service}_{timestamp}.log"
            log_file_path.write_text(result.stdout, encoding="utf-8")
        else:
            console.print(f"[red]No logs found for service {service}.[/red]")

    collect_database_logs(
        context=context, database=database, namespace=namespace, logs_dir=logs_dir, include_queries=include_queries
    )
    collect_message_queue_status(context=context, database=database, namespace=namespace, logs_dir=logs_dir)
    collect_cache_status(context=context, database=database, namespace=namespace, logs_dir=logs_dir)
    collect_task_worker_status(context=context, database=database, namespace=namespace, logs_dir=logs_dir)

    console.print("[bold yellow]Collecting system metrics[/bold yellow]")
    sys_metrics = collect_system_metrics()
    metrics_file = Path(logs_dir) / f"system_metrics_{timestamp}.json"
    metrics_file.write_text(json.dumps(sys_metrics, indent=2), encoding="utf-8")

    console.print("[bold yellow]Collecting container metrics[/bold yellow]")
    with context.cd(ESCAPED_REPO_PATH):
        compose_files_cmd = build_compose_files_cmd(database=database, namespace=namespace)
        compose_cmd = get_compose_cmd(namespace=namespace)
        base_cmd = f"{get_env_vars(context, namespace=namespace)} {compose_cmd} {compose_files_cmd} -p {BUILD_NAME}"

        stats_result = execute_command(context=context, command=f"{base_cmd} stats --no-stream --no-trunc", hide=True)

        if stats_result and stats_result.stdout:
            containers_metrics = []
            lines = stats_result.stdout.strip().split("\n")[1:]
            for line in lines:
                stats = parse_docker_stats_line(line)
                if stats:
                    name, cpu, mem_usage, mem_percent, net_io, block_io, pids = stats
                    containers_metrics.append(
                        {
                            "name": name,
                            "cpu_usage": cpu,
                            "memory_usage": mem_usage,
                            "memory_percent": mem_percent,
                            "network_io": net_io,
                            "block_io": block_io,
                            "pids": pids,
                        }
                    )

            container_metrics_file = Path(logs_dir) / f"container_metrics_{timestamp}.json"
            container_metrics_file.write_text(json.dumps(containers_metrics, indent=2), encoding="utf-8")

    archive_name = f"support_logs_{timestamp}.tar.gz"
    shutil.make_archive(base_name=f"support_logs_{timestamp}", format="gztar", root_dir=".", base_dir=logs_dir)
    shutil.rmtree(logs_dir)

    console.print(f"[green]Archive successfully created: {archive_name}[/green]")
    console.print("You can now provide this file for support analysis.")
