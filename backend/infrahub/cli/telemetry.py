from dataclasses import asdict

import typer
import ujson
from infrahub_sdk.async_typer import AsyncTyper
from rich.console import Console
from rich.table import Table

from infrahub.telemetry.resources import ProcessResources, ResourceDiagnostics

app = AsyncTyper()


@app.callback()
def callback() -> None:
    """Inspect what telemetry reports about this deployment."""


def _format_bytes(value: int | None) -> str:
    if value is None:
        return "null (unbounded / unknown)"
    return f"{value} ({value / 1024**3:.2f} GiB)"


def _render(diagnostics: ResourceDiagnostics, console: Console) -> None:
    reading = diagnostics.reading

    reported = Table(title="Reported to telemetry", show_header=False, title_justify="left")
    reported.add_column(style="bold")
    reported.add_column()
    reported.add_row("processor_available", str(reading.processor_available))
    reported.add_row(
        "processor_assigned",
        "null (no enforced CPU limit)" if reading.processor_assigned is None else str(reading.processor_assigned),
    )
    reported.add_row("memory_total", _format_bytes(reading.memory_total))
    reported.add_row("memory_available", _format_bytes(reading.memory_available))
    console.print(reported)

    host = Table(title="Whole host, for comparison", show_header=False, title_justify="left")
    host.add_column(style="bold")
    host.add_column()
    host.add_row("logical processors", str(diagnostics.host_processor_available))
    host.add_row("memory total", _format_bytes(diagnostics.host_memory_total))
    console.print(host)

    if reading.memory_total == diagnostics.host_memory_total:
        console.print(
            "[yellow]memory_total matches the whole host: no memory limit is enforced on this process, "
            "so the figure is host capacity rather than an allocation.[/yellow]"
        )

    environment = Table(title="Environment", show_header=False, title_justify="left")
    environment.add_column(style="bold")
    environment.add_column()
    environment.add_row("hostname (dedup key)", reading.host)
    environment.add_row("cgroup v2 at root", str(diagnostics.cgroup_v2_root))
    environment.add_row("cgroup v1 at root", str(diagnostics.cgroup_v1_root))
    environment.add_row("proc cgroup", diagnostics.proc_cgroup or "unreadable")
    console.print(environment)

    levels = Table(title="Resolved cgroup levels (leaf first)", title_justify="left")
    levels.add_column("path")
    levels.add_column("limit files found")
    for level in diagnostics.levels:
        contents = ", ".join(f"{name}={content}" for name, content in level.files.items())
        levels.add_row(level.path, contents or "[dim]none[/dim]")
    console.print(levels)


@app.command(name="probe-resources")
def probe_resources(
    as_json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON instead of tables."),
) -> None:
    """Report the CPU and memory allocation this process sees, and the evidence behind it.

    Reads only the local process's own control group and needs no database, cache
    or configuration, so it can explain an environment whose reported figures
    look wrong even when the deployment is otherwise unhealthy. Nothing is
    transmitted; the output goes to stdout.
    """
    diagnostics = ProcessResources().diagnose()

    if as_json:
        payload = asdict(diagnostics) | {"reading": diagnostics.reading.model_dump()}
        # Paths are the point of this output, so keep the slashes unescaped for a reader.
        print(ujson.dumps(payload, indent=2, escape_forward_slashes=False))
        return

    _render(diagnostics=diagnostics, console=Console())
