# Preference models

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Self

from infrahub import lock
from infrahub.core.node.standard import StandardNode
from infrahub.core.query.preference import UserPreferenceGetByAccountQuery

if TYPE_CHECKING:
    from infrahub.core.query import Query
    from infrahub.database import InfrahubDatabase

# Well-known distributed-lock coordinates for the GlobalPreference singleton. A fixed name in a
# dedicated namespace lets every worker serialise the lazy-create through the same global lock.
GLOBAL_PREFERENCE_LOCK_NAME = "singleton"
GLOBAL_PREFERENCE_LOCK_NAMESPACE = "global_preference"


class GlobalPreference(StandardNode):
    # Persisted nullable fields must use `Optional[X]` rather than `X | None` until we move to
    # Python 3.14 b/c of how StandardNode.guess_field_type works (mirrors Branch).
    date_format: Optional[str] = None
    timezone: Optional[str] = None

    @classmethod
    async def get_global(cls, db: InfrahubDatabase) -> Self:
        """Return the singleton GlobalPreference, lazily creating an empty one if none exists.

        GlobalPreference is a 0..1 singleton. New installs seed it in `first_time_initialization`,
        so on those the fast path below returns without ever taking a lock. Pre-existing installs
        (upgraded before the seed existed) materialise it lazily here.

        This runs on every effective-preferences READ, so the lazy create uses double-checked
        locking to avoid a singleton race: the fast path reads with no lock and returns if present;
        only when absent do we acquire a well-known distributed lock, RE-READ inside it, and create
        only if still absent. If duplicates somehow exist, `get_list` orders deterministically by id
        so we keep returning the first — but the lock prevents creating them in the first place.
        """
        existing = await cls.get_list(db=db, limit=1)
        if existing:
            return existing[0]

        async with lock.registry.get(
            name=GLOBAL_PREFERENCE_LOCK_NAME, namespace=GLOBAL_PREFERENCE_LOCK_NAMESPACE, local=False
        ):
            # Re-read inside the lock: another worker may have created it while we waited.
            existing = await cls.get_list(db=db, limit=1)
            if existing:
                return existing[0]

            obj = cls()
            await obj.create(db=db)
            return obj


class UserPreference(StandardNode):
    # Orphan-on-account-deletion is accepted for V1: a StandardNode cannot declare a schema
    # relationship with `on_delete: cascade` (that is a schema-Node feature), so deleting an
    # account leaves its UserPreference row behind. Account ids are UUIDs (UUIDT) and are never
    # reused, so such a row is permanently unreachable dead data — benign. Cleanup is out of scope
    # for V1; there is no cascade mechanism for StandardNode and we deliberately do not convert this
    # to a schema node.
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
