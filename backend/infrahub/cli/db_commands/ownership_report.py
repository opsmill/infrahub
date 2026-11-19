from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import Console

from infrahub.core.ownership.report import build_ownership_report

if TYPE_CHECKING:
    from infrahub.database import InfrahubDatabase


def _print_section(console: Console, title: str, lines: list[str]) -> None:
    for line in ["", f"{title}: {len(lines)}", *(f"  {line}" for line in lines)]:
        console.print(line, markup=False, highlight=False, soft_wrap=True)


async def ownership_report(db: InfrahubDatabase) -> None:
    """Print the data whose meaning changes with node owners. The database is not changed."""
    report = await build_ownership_report(db=db)
    console = Console()
    _print_section(
        console,
        title="Attributes that a repository owns (the upgrade removes these owners)",
        lines=[
            f"{row.node_kind}.{row.attribute_name}, repository {row.repository_id} ({row.repository_kind}),"
            f" branch {row.branch}: {row.nb_attributes}"
            for row in report.repository_owners
        ],
    )
    _print_section(
        console,
        title=(
            "Attributes that a node other than an account, an account group or a repository owns"
            " (the upgrade keeps these owners)"
        ),
        lines=[
            f"{row.owner_kind} owns {row.node_kind}.{row.attribute_name}, branch {row.branch}: {row.nb_attributes}"
            for row in report.other_owners
        ],
    )
    _print_section(
        console,
        title="Relationships whose links have owners (the upgrade keeps these owners)",
        lines=[
            f"{row.identifier} ({', '.join(row.peer_kinds)}), owner kind {row.owner_kind},"
            f" branch {row.branch}: {row.nb_links}"
            for row in report.link_owners
        ],
    )
    _print_section(
        console,
        title="Attributes with values that have is_protected set (is_protected is deprecated)",
        lines=[
            f"{row.node_kind}.{row.attribute_name}, branch {row.branch}: {row.nb_values}"
            for row in report.protected_values
        ],
    )
