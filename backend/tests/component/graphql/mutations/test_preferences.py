from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.auth.session import AnonymousSession
from infrahub.core.constants import InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.graphql.initialization import prepare_graphql_params
from tests.helpers.graphql import graphql

if TYPE_CHECKING:
    from graphql import ExecutionResult

    from infrahub.auth.session import AccountSession
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

USER_PREFERENCE_UPSERT = """
mutation UserPreferenceUpsert($account_id: String!, $date_format: String) {
  CoreUserPreferenceUpsert(data: {
    account: {id: $account_id}
    date_format: {value: $date_format}
  }) {
    ok
    object {
      id
    }
  }
}
"""

USER_PREFERENCE_UPSERT_TIMEZONE = """
mutation UserPreferenceUpsertTimezone($account_id: String!, $timezone: String) {
  CoreUserPreferenceUpsert(data: {
    account: {id: $account_id}
    timezone: {value: $timezone}
  }) {
    ok
    object {
      id
    }
  }
}
"""

USER_PREFERENCE_UPSERT_WITH_ID = """
mutation UserPreferenceUpsertWithId($id: String!, $date_format: String) {
  CoreUserPreferenceUpsert(data: {
    id: $id
    date_format: {value: $date_format}
  }) {
    ok
  }
}
"""

USER_PREFERENCE_UPSERT_ACCOUNT_BY_HFID = """
mutation UserPreferenceUpsertAccountByHfid($account_hfid: String!, $timezone: String) {
  CoreUserPreferenceUpsert(data: {
    account: {hfid: [$account_hfid]}
    timezone: {value: $timezone}
  }) {
    ok
  }
}
"""

USER_PREFERENCE_UPDATE_ACCOUNT = """
mutation UserPreferenceUpdateAccount($id: String!, $account_id: String!) {
  CoreUserPreferenceUpdate(data: {
    id: $id
    account: {id: $account_id}
  }) {
    ok
  }
}
"""

USER_PREFERENCE_UPDATE = """
mutation UserPreferenceUpdate($id: String!, $date_format: String) {
  CoreUserPreferenceUpdate(data: {
    id: $id
    date_format: {value: $date_format}
  }) {
    ok
  }
}
"""

USER_PREFERENCE_DELETE = """
mutation UserPreferenceDelete($id: String!) {
  CoreUserPreferenceDelete(data: {id: $id}) {
    ok
  }
}
"""

GLOBAL_PREFERENCE_CREATE = """
mutation {
  CoreGlobalPreferenceCreate(data: {
    date_format: {value: "yyyy-MM-dd"}
  }) {
    ok
  }
}
"""

GLOBAL_PREFERENCE_UPSERT_WITHOUT_ID = """
mutation {
  CoreGlobalPreferenceUpsert(data: {
    date_format: {value: "yyyy-MM-dd"}
  }) {
    ok
  }
}
"""


async def _run_mutation(
    db: InfrahubDatabase,
    branch: Branch,
    account_session: AccountSession | None,
    query: str,
    variables: dict | None = None,
) -> ExecutionResult:
    gql_params = await prepare_graphql_params(
        db=db, branch=branch, account_session=account_session, include_mutation=True
    )
    return await graphql(
        schema=gql_params.schema,
        source=query,
        context_value=gql_params.context,
        root_value=None,
        variable_values=variables or {},
    )


async def _create_user_preference(db: InfrahubDatabase, account: Node, date_format: str | None = None) -> Node:
    obj = await Node.init(db=db, schema=InfrahubKind.USERPREFERENCE)
    await obj.new(db=db, account=account, date_format=date_format)
    await obj.save(db=db)
    return obj


class TestUserPreferenceOwnerScoping:
    async def test_owner_lazy_upsert_creates_row(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: None,
        default_permission_backend: None,
        first_account: Node,
        session_first_account: AccountSession,
    ) -> None:
        default_branch.update_schema_hash()
        result = await _run_mutation(
            db=db,
            branch=default_branch,
            account_session=session_first_account,
            query=USER_PREFERENCE_UPSERT,
            variables={"account_id": first_account.id, "date_format": "dd/MM/yyyy"},
        )

        assert result.errors is None
        assert result.data
        assert result.data["CoreUserPreferenceUpsert"]["ok"] is True

        rows = await NodeManager.query(
            db=db, schema=InfrahubKind.USERPREFERENCE, filters={"account__ids": [first_account.id]}
        )
        assert len(rows) == 1
        assert rows[0].date_format.value == "dd/MM/yyyy"

    async def test_owner_lazy_upsert_is_idempotent(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: None,
        default_permission_backend: None,
        first_account: Node,
        session_first_account: AccountSession,
    ) -> None:
        default_branch.update_schema_hash()
        for timezone in ("UTC", "Europe/Paris"):
            result = await _run_mutation(
                db=db,
                branch=default_branch,
                account_session=session_first_account,
                query=USER_PREFERENCE_UPSERT_TIMEZONE,
                variables={"account_id": first_account.id, "timezone": timezone},
            )

            assert result.errors is None, result.errors
            assert result.data
            assert result.data["CoreUserPreferenceUpsert"]["ok"] is True

        rows = await NodeManager.query(
            db=db, schema=InfrahubKind.USERPREFERENCE, filters={"account__ids": [first_account.id]}
        )
        assert len(rows) == 1
        assert rows[0].timezone.value == "Europe/Paris"

    async def test_owner_upsert_account_by_hfid_rejected_with_clear_error(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: None,
        default_permission_backend: None,
        first_account: Node,
        session_first_account: AccountSession,
    ) -> None:
        default_branch.update_schema_hash()
        result = await _run_mutation(
            db=db,
            branch=default_branch,
            account_session=session_first_account,
            query=USER_PREFERENCE_UPSERT_ACCOUNT_BY_HFID,
            variables={"account_hfid": first_account.name.value, "timezone": "UTC"},
        )

        assert result.errors
        assert any("account must be specified by id" in str(error) for error in result.errors)

    async def test_non_owner_upsert_with_id_of_other_row_denied(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: None,
        default_permission_backend: None,
        first_account: Node,
        second_account: Node,
        session_first_account: AccountSession,
    ) -> None:
        default_branch.update_schema_hash()
        other_row = await _create_user_preference(db=db, account=second_account, date_format="relative")

        result = await _run_mutation(
            db=db,
            branch=default_branch,
            account_session=session_first_account,
            query=USER_PREFERENCE_UPSERT_WITH_ID,
            variables={"id": other_row.id, "date_format": "yyyy-MM-dd"},
        )

        assert result.errors
        assert any("preferences of another account" in str(error) for error in result.errors)

        unchanged = await NodeManager.get_one(db=db, id=other_row.id)
        assert unchanged.date_format.value == "relative"

    async def test_owner_cannot_repoint_row_to_another_account(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: None,
        default_permission_backend: None,
        first_account: Node,
        second_account: Node,
        session_first_account: AccountSession,
    ) -> None:
        default_branch.update_schema_hash()
        row = await _create_user_preference(db=db, account=first_account, date_format="relative")

        result = await _run_mutation(
            db=db,
            branch=default_branch,
            account_session=session_first_account,
            query=USER_PREFERENCE_UPDATE_ACCOUNT,
            variables={"id": row.id, "account_id": second_account.id},
        )

        assert result.errors
        assert any("preferences of another account" in str(error) for error in result.errors)

        unchanged = await NodeManager.get_one(db=db, id=row.id)
        owner = await unchanged.account.get_peer(db=db)
        assert owner is not None
        assert owner.id == first_account.id

    async def test_non_owner_lazy_upsert_with_foreign_account_peer_denied(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: None,
        default_permission_backend: None,
        first_account: Node,
        second_account: Node,
        session_first_account: AccountSession,
    ) -> None:
        """Ownership-contract guard: the id-less account-peer resolution path must validate the owner.

        Together with test_non_owner_upsert_with_id_of_other_row_denied (explicit foreign id) this
        locks ownership on every _resolve_existing_node path. If a future change lets the account
        uniqueness-key lookup skip _validate_row_owner, this fails loudly.
        """
        default_branch.update_schema_hash()
        other_row = await _create_user_preference(db=db, account=second_account, date_format="relative")

        result = await _run_mutation(
            db=db,
            branch=default_branch,
            account_session=session_first_account,
            query=USER_PREFERENCE_UPSERT,
            variables={"account_id": second_account.id, "date_format": "yyyy-MM-dd"},
        )

        assert result.errors
        assert any("preferences of another account" in str(error) for error in result.errors)

        unchanged = await NodeManager.get_one(db=db, id=other_row.id)
        assert unchanged.date_format.value == "relative"

    async def test_non_owner_cannot_create_for_other_account(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: None,
        default_permission_backend: None,
        first_account: Node,
        second_account: Node,
        session_first_account: AccountSession,
    ) -> None:
        default_branch.update_schema_hash()
        result = await _run_mutation(
            db=db,
            branch=default_branch,
            account_session=session_first_account,
            query=USER_PREFERENCE_UPSERT,
            variables={"account_id": second_account.id, "date_format": "relative"},
        )

        assert result.errors
        assert any("preferences of another account" in str(error) for error in result.errors)

    async def test_non_owner_update_denied(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: None,
        default_permission_backend: None,
        first_account: Node,
        second_account: Node,
        session_first_account: AccountSession,
    ) -> None:
        default_branch.update_schema_hash()
        other_row = await _create_user_preference(db=db, account=second_account, date_format="relative")

        result = await _run_mutation(
            db=db,
            branch=default_branch,
            account_session=session_first_account,
            query=USER_PREFERENCE_UPDATE,
            variables={"id": other_row.id, "date_format": "yyyy-MM-dd"},
        )

        assert result.errors
        assert any("preferences of another account" in str(error) for error in result.errors)

        unchanged = await NodeManager.get_one(db=db, id=other_row.id)
        assert unchanged.date_format.value == "relative"

    async def test_non_owner_delete_denied(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: None,
        default_permission_backend: None,
        first_account: Node,
        second_account: Node,
        session_first_account: AccountSession,
    ) -> None:
        default_branch.update_schema_hash()
        rows = await NodeManager.query(
            db=db, schema=InfrahubKind.USERPREFERENCE, filters={"account__ids": [second_account.id]}
        )
        other_row = rows[0] if rows else await _create_user_preference(db=db, account=second_account)

        result = await _run_mutation(
            db=db,
            branch=default_branch,
            account_session=session_first_account,
            query=USER_PREFERENCE_DELETE,
            variables={"id": other_row.id},
        )

        assert result.errors
        assert any("preferences of another account" in str(error) for error in result.errors)

        unchanged = await NodeManager.get_one(db=db, id=other_row.id)
        assert unchanged is not None

    async def test_admin_can_write_any_row(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: None,
        default_permission_backend: None,
        first_account: Node,
        session_admin: AccountSession,
    ) -> None:
        default_branch.update_schema_hash()
        rows = await NodeManager.query(
            db=db, schema=InfrahubKind.USERPREFERENCE, filters={"account__ids": [first_account.id]}
        )
        row = rows[0] if rows else await _create_user_preference(db=db, account=first_account)

        result = await _run_mutation(
            db=db,
            branch=default_branch,
            account_session=session_admin,
            query=USER_PREFERENCE_UPDATE,
            variables={"id": row.id, "date_format": "relative"},
        )

        assert result.errors is None
        assert result.data
        assert result.data["CoreUserPreferenceUpdate"]["ok"] is True

        updated = await NodeManager.get_one(db=db, id=row.id)
        assert updated.date_format.value == "relative"

    async def test_admin_upsert_account_by_hfid_is_idempotent(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: None,
        default_permission_backend: None,
        second_account: Node,
        session_admin: AccountSession,
    ) -> None:
        default_branch.update_schema_hash()
        for timezone in ("UTC", "Europe/Paris"):
            result = await _run_mutation(
                db=db,
                branch=default_branch,
                account_session=session_admin,
                query=USER_PREFERENCE_UPSERT_ACCOUNT_BY_HFID,
                variables={"account_hfid": second_account.name.value, "timezone": timezone},
            )

            assert result.errors is None, result.errors
            assert result.data
            assert result.data["CoreUserPreferenceUpsert"]["ok"] is True

        rows = await NodeManager.query(
            db=db, schema=InfrahubKind.USERPREFERENCE, filters={"account__ids": [second_account.id]}
        )
        assert len(rows) == 1
        assert rows[0].timezone.value == "Europe/Paris"

    async def test_unauthenticated_session_denied(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: None,
        default_permission_backend: None,
        first_account: Node,
    ) -> None:
        """An unauthenticated (no account_session) caller is rejected by the fail-closed guard."""
        default_branch.update_schema_hash()
        result = await _run_mutation(
            db=db,
            branch=default_branch,
            account_session=None,
            query=USER_PREFERENCE_UPSERT,
            variables={"account_id": first_account.id, "date_format": "dd/MM/yyyy"},
        )

        assert result.errors
        assert any("preferences of another account" in str(error) for error in result.errors)

        rows = await NodeManager.query(
            db=db, schema=InfrahubKind.USERPREFERENCE, filters={"account__ids": [first_account.id]}
        )
        assert rows == []

    async def test_anonymous_session_denied(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: None,
        default_permission_backend: None,
        first_account: Node,
    ) -> None:
        """An anonymous (unauthenticated) session is rejected by the fail-closed guard."""
        default_branch.update_schema_hash()
        result = await _run_mutation(
            db=db,
            branch=default_branch,
            account_session=AnonymousSession(),
            query=USER_PREFERENCE_UPSERT,
            variables={"account_id": first_account.id, "date_format": "dd/MM/yyyy"},
        )

        assert result.errors

        rows = await NodeManager.query(
            db=db, schema=InfrahubKind.USERPREFERENCE, filters={"account__ids": [first_account.id]}
        )
        assert rows == []


class TestGlobalPreferenceSingletonGuard:
    async def test_create_refused_when_singleton_exists(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: None,
        default_permission_backend: None,
        session_admin: AccountSession,
    ) -> None:
        default_branch.update_schema_hash()
        existing = await Node.init(db=db, schema=InfrahubKind.GLOBALPREFERENCE)
        await existing.new(db=db)
        await existing.save(db=db)

        result = await _run_mutation(
            db=db, branch=default_branch, account_session=session_admin, query=GLOBAL_PREFERENCE_CREATE
        )

        assert result.errors
        assert any("singleton" in str(error) for error in result.errors)

        rows = await NodeManager.query(db=db, schema=InfrahubKind.GLOBALPREFERENCE)
        assert len(rows) == 1

    async def test_upsert_without_id_refused_when_singleton_exists(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: None,
        default_permission_backend: None,
        session_admin: AccountSession,
    ) -> None:
        default_branch.update_schema_hash()
        rows = await NodeManager.query(db=db, schema=InfrahubKind.GLOBALPREFERENCE, limit=1)
        if not rows:
            existing = await Node.init(db=db, schema=InfrahubKind.GLOBALPREFERENCE)
            await existing.new(db=db)
            await existing.save(db=db)

        result = await _run_mutation(
            db=db, branch=default_branch, account_session=session_admin, query=GLOBAL_PREFERENCE_UPSERT_WITHOUT_ID
        )

        assert result.errors
        assert any("singleton" in str(error) for error in result.errors)

        rows = await NodeManager.query(db=db, schema=InfrahubKind.GLOBALPREFERENCE)
        assert len(rows) == 1

    async def test_create_allowed_when_no_singleton_exists(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        register_core_models_schema: None,
        default_permission_backend: None,
        session_admin: AccountSession,
    ) -> None:
        default_branch.update_schema_hash()
        for row in await NodeManager.query(db=db, schema=InfrahubKind.GLOBALPREFERENCE):
            await row.delete(db=db)

        result = await _run_mutation(
            db=db, branch=default_branch, account_session=session_admin, query=GLOBAL_PREFERENCE_CREATE
        )

        assert result.errors is None
        assert result.data
        assert result.data["CoreGlobalPreferenceCreate"]["ok"] is True

        rows = await NodeManager.query(db=db, schema=InfrahubKind.GLOBALPREFERENCE)
        assert len(rows) == 1
