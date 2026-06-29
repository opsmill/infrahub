# Preference models

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Self

from infrahub.core.node.standard import StandardNode
from infrahub.core.query.preference import UserPreferenceGetByAccountQuery

if TYPE_CHECKING:
    from infrahub.core.query import Query
    from infrahub.database import InfrahubDatabase


class GlobalPreference(StandardNode):
    # Persisted nullable fields must use `Optional[X]` rather than `X | None` until we move to
    # Python 3.14 b/c of how StandardNode.guess_field_type works (mirrors Branch).
    date_format: Optional[str] = None
    timezone: Optional[str] = None

    @classmethod
    async def get_global(cls, db: InfrahubDatabase) -> Self:
        """Return the singleton GlobalPreference, lazily creating an empty one if none exists.

        GlobalPreference is a 0..1 singleton: there is no migration that seeds it, so the first
        read materialises an empty instance (mirrors how `get_global()` is described in the spec).
        """
        existing = await cls.get_list(db=db, limit=1)
        if existing:
            return existing[0]

        obj = cls()
        await obj.create(db=db)
        return obj


class UserPreference(StandardNode):
    account_id: str
    # Persisted nullable fields must use `Optional[X]` (see GlobalPreference).
    date_format: Optional[str] = None
    timezone: Optional[str] = None

    @classmethod
    async def get_for_account(cls, db: InfrahubDatabase, account_id: str) -> Self | None:
        """Return the single UserPreference owned by `account_id`, or None if the account has none.

        Uses a targeted Cypher lookup (UserPreferenceGetByAccountQuery) rather than listing every
        row and filtering in Python, so we never scan other users' preferences.
        """
        query: Query = await UserPreferenceGetByAccountQuery.init(
            db=db, account_id=account_id, node_type=cls.get_type()
        )
        await query.execute(db=db)

        result = query.get_result()
        if not result:
            return None

        return cls.from_db(result.get_node("n"))
