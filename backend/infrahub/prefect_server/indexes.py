from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

INDEXED_RESOURCE_LABELS: tuple[str, ...] = (
    "infrahub.event.level",
    "infrahub.event.has_children",
    "infrahub.branch.name",
    "infrahub.node.id",
    "infrahub.resource.label",
    "infrahub.resource.id",
    "infrahub.event_parent.id",
)


def _index_name(label: str) -> str:
    slug = label.replace(".", "_")
    return f"ix_event_resources__resource__{slug}"


async def create_custom_indexes(session: AsyncSession) -> None:
    bind = session.get_bind()
    if bind.dialect.name != "postgresql":
        return

    statements: list[str] = [
        "CREATE INDEX IF NOT EXISTS ix_event_resources__resource_role ON event_resources USING btree (resource_role)"
    ]
    for label in INDEXED_RESOURCE_LABELS:
        statements.append(
            f"CREATE INDEX IF NOT EXISTS {_index_name(label)} ON event_resources USING btree ((resource ->> '{label}'))"
        )

    for stmt in statements:
        await session.execute(text(stmt))
    await session.commit()
