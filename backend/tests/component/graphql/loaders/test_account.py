"""Unit tests for AccountDataLoader.

These tests verify that AccountDataLoader correctly:
- Handles SYSTEM_USER_ID by returning synthetic system account data
- Loads real accounts from the database
- Returns placeholder data for unknown/deleted accounts
- Caches results to avoid duplicate database lookups within a request
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from infrahub.core.constants import SYSTEM_USER_ID, InfrahubKind
from infrahub.core.node import Node
from infrahub.core.timestamp import Timestamp
from infrahub.graphql.loaders.account import (
    SYSTEM_ACCOUNT_DISPLAY_LABEL,
    UNKNOWN_ACCOUNT_DISPLAY_LABEL,
    AccountDataLoader,
    AccountLoaderParams,
)

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


@pytest.fixture
async def test_account(db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch) -> Node:
    """Create a test account for loader tests."""
    obj = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
    await obj.new(db=db, name="Test Account", account_type="User", password="TestPassword123")
    await obj.save(db=db)
    return obj


async def test_system_user_returns_synthetic_data(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """Verify SYSTEM_USER_ID returns synthetic system account data.

    When loading SYSTEM_USER_ID, the loader should return a synthetic response
    with [Infrahub System] as the display label and CoreAccount as the typename.
    """
    params = AccountLoaderParams(
        branch=default_branch,
        at=None,
        fields={"id": {}, "display_label": {}, "__typename": {}},
    )
    loader = AccountDataLoader(db=db, params=params)

    result = await loader.load(SYSTEM_USER_ID)

    assert result is not None
    assert result["id"] == SYSTEM_USER_ID
    assert result["display_label"] == SYSTEM_ACCOUNT_DISPLAY_LABEL
    assert result["__typename"] == InfrahubKind.ACCOUNT


async def test_real_account_loads_from_database(
    db: InfrahubDatabase,
    default_branch: Branch,
    test_account: Node,
) -> None:
    """Verify real account IDs are loaded from the database.

    When loading a real account ID, the loader should query the database
    and return the account data with proper display_label.
    """
    params = AccountLoaderParams(
        branch=default_branch,
        at=None,
        fields={"id": {}, "display_label": {}, "__typename": {}},
    )
    loader = AccountDataLoader(db=db, params=params)

    result = await loader.load(test_account.id)

    assert result is not None
    assert result["id"] == test_account.id
    assert result["display_label"] == "Test Account"
    assert result["__typename"] == InfrahubKind.ACCOUNT


async def test_unknown_account_returns_placeholder(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """Verify unknown/deleted accounts return a placeholder response.

    When loading an account ID that doesn't exist in the database,
    the loader should return placeholder data with [Unknown Account]
    as the display label instead of None or raising an error.
    """
    params = AccountLoaderParams(
        branch=default_branch,
        at=None,
        fields={"id": {}, "display_label": {}, "__typename": {}},
    )
    loader = AccountDataLoader(db=db, params=params)

    unknown_id = "non-existent-account-id"
    result = await loader.load(unknown_id)

    assert result is not None
    assert result["id"] == unknown_id
    assert result["display_label"] == UNKNOWN_ACCOUNT_DISPLAY_LABEL
    assert result["__typename"] == InfrahubKind.ACCOUNT


async def test_caching_returns_same_result_object(
    db: InfrahubDatabase,
    default_branch: Branch,
    test_account: Node,
) -> None:
    """Verify that loading the same account ID twice returns cached results.

    DataLoader should cache results from the first load. When loading the
    same ID a second time, it should return the exact same result object
    (identity check), demonstrating that caching is working.
    """
    params = AccountLoaderParams(
        branch=default_branch,
        at=None,
        fields={"id": {}, "display_label": {}},
    )
    loader = AccountDataLoader(db=db, params=params)

    result1 = await loader.load(test_account.id)
    result2 = await loader.load(test_account.id)

    # Results should be the exact same object due to caching
    assert result1 is result2
    assert result1["display_label"] == "Test Account"


async def test_batch_loading_multiple_accounts(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """Verify multiple accounts can be loaded in a single batch.

    When loading multiple account IDs, the loader should batch them
    and return results in the correct order.
    """
    # Create multiple test accounts
    accounts = []
    for i in range(3):
        obj = await Node.init(db=db, schema=InfrahubKind.ACCOUNT)
        await obj.new(db=db, name=f"Batch Account {i}", account_type="User", password="TestPassword123")
        await obj.save(db=db)
        accounts.append(obj)

    params = AccountLoaderParams(
        branch=default_branch,
        at=None,
        fields={"id": {}, "display_label": {}},
    )
    loader = AccountDataLoader(db=db, params=params)

    account_ids = [acc.id for acc in accounts]
    results = await loader.load_many(account_ids)

    assert len(results) == 3
    for i, result in enumerate(results):
        assert result is not None
        assert result["id"] == accounts[i].id
        assert result["display_label"] == f"Batch Account {i}"


async def test_mixed_system_and_real_accounts(
    db: InfrahubDatabase,
    default_branch: Branch,
    test_account: Node,
) -> None:
    """Verify loading a mix of system user and real accounts.

    When loading both SYSTEM_USER_ID and real account IDs together,
    the loader should return synthetic data for the system user and
    database-loaded data for real accounts.
    """
    params = AccountLoaderParams(
        branch=default_branch,
        at=None,
        fields={"id": {}, "display_label": {}},
    )
    loader = AccountDataLoader(db=db, params=params)

    results = await loader.load_many([SYSTEM_USER_ID, test_account.id])

    assert len(results) == 2
    assert results[0] is not None
    assert results[0]["id"] == SYSTEM_USER_ID
    assert results[0]["display_label"] == SYSTEM_ACCOUNT_DISPLAY_LABEL
    assert results[1] is not None
    assert results[1]["id"] == test_account.id
    assert results[1]["display_label"] == "Test Account"


async def test_system_user_name_field_returns_display_label(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """Verify SYSTEM_USER_ID returns proper name field structure.

    When the 'name' field is requested for the system user,
    it should return a dict with 'value' containing the display label.
    """
    params = AccountLoaderParams(
        branch=default_branch,
        at=None,
        fields={"id": {}, "name": {}},
    )
    loader = AccountDataLoader(db=db, params=params)

    result = await loader.load(SYSTEM_USER_ID)

    assert result is not None
    assert result["name"] == {"value": SYSTEM_ACCOUNT_DISPLAY_LABEL}


async def test_loader_params_hash_excludes_fields(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """Verify AccountLoaderParams hash is based on branch and timestamp, not fields.

    The hash should be consistent across different field selections so that
    loaders with the same branch/timestamp can be reused.
    """

    timestamp = Timestamp()

    params1 = AccountLoaderParams(branch=default_branch, at=timestamp, fields={"id": {}})
    params2 = AccountLoaderParams(branch=default_branch, at=timestamp, fields={"id": {}, "display_label": {}})

    assert hash(params1) == hash(params2)
