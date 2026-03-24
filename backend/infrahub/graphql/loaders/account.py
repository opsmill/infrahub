"""DataLoader for resolving account IDs to full account data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from aiodataloader import DataLoader

from infrahub.core.constants import SYSTEM_USER_ID, InfrahubKind
from infrahub.core.manager import NodeManager
from infrahub.graphql.constants import KIND_GRAPHQL_FIELD_NAME

if TYPE_CHECKING:
    from infrahub.core.branch.models import Branch
    from infrahub.core.timestamp import Timestamp
    from infrahub.database import InfrahubDatabase

SYSTEM_ACCOUNT_DISPLAY_LABEL = "[Infrahub System]"
UNKNOWN_ACCOUNT_DISPLAY_LABEL = "[Unknown Account]"


@dataclass
class AccountLoaderParams:
    branch: Branch
    at: Timestamp | None
    fields: dict[str, Any] = field(default_factory=dict)

    def __hash__(self) -> int:
        # Fields are not included in hash as they vary per query but we want to reuse loader
        at_str = self.at.to_string() if self.at else ""
        return hash(f"{at_str}|{self.branch.name}")


class AccountDataLoader(DataLoader[str, dict[str, Any] | None]):
    """DataLoader for batch-loading account data by ID.

    Handles SYSTEM_USER_ID specially by returning synthetic system account data.
    All lookups are branch-agnostic since accounts don't vary by branch.
    """

    def __init__(
        self,
        db: InfrahubDatabase,
        params: AccountLoaderParams,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.db = db
        self.params = params

    def _build_system_account_response(self, fields: dict[str, Any]) -> dict[str, Any]:
        """Build response for SYSTEM_USER_ID based on requested fields."""
        # Always include __kind__ for GraphQL interface type resolution
        response: dict[str, Any] = {KIND_GRAPHQL_FIELD_NAME: InfrahubKind.ACCOUNT}

        for field_name in fields:
            if field_name == "id":
                response["id"] = SYSTEM_USER_ID
            elif field_name == "display_label":
                response["display_label"] = SYSTEM_ACCOUNT_DISPLAY_LABEL
            elif field_name == "__typename":
                response["__typename"] = InfrahubKind.ACCOUNT
            elif field_name == "name":
                response["name"] = {"value": SYSTEM_ACCOUNT_DISPLAY_LABEL}
            elif field_name == "label":
                response["label"] = {"value": SYSTEM_ACCOUNT_DISPLAY_LABEL}
            elif field_name == "description":
                response["description"] = {"value": None}
            else:
                # For any other field, return None
                response[field_name] = None

        return response

    def _build_unknown_account_response(self, account_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Build response for an unknown/deleted account based on requested fields."""
        # Always include __kind__ for GraphQL interface type resolution
        response: dict[str, Any] = {KIND_GRAPHQL_FIELD_NAME: InfrahubKind.ACCOUNT}

        for field_name in fields:
            if field_name == "id":
                response["id"] = account_id
            elif field_name == "display_label":
                response["display_label"] = UNKNOWN_ACCOUNT_DISPLAY_LABEL
            elif field_name == "__typename":
                response["__typename"] = InfrahubKind.ACCOUNT
            elif field_name == "name":
                response["name"] = {"value": UNKNOWN_ACCOUNT_DISPLAY_LABEL}
            elif field_name == "label":
                response["label"] = {"value": UNKNOWN_ACCOUNT_DISPLAY_LABEL}
            elif field_name == "description":
                response["description"] = {"value": None}
            else:
                response[field_name] = None

        return response

    async def batch_load_fn(self, keys: list[str]) -> list[dict[str, Any] | None]:
        # Separate system user from real account IDs
        real_account_ids = [k for k in keys if k != SYSTEM_USER_ID]

        # Batch load real accounts
        accounts_by_id: dict[str, dict[str, Any]] = {}
        if real_account_ids:
            async with self.db.start_session(read_only=True) as db:
                nodes = await NodeManager.get_many(
                    db=db,
                    ids=real_account_ids,
                    fields=self.params.fields,
                    at=self.params.at,
                    branch=self.params.branch,
                    branch_agnostic=True,  # Accounts are always branch-agnostic
                )

                for node_id, node in nodes.items():
                    accounts_by_id[node_id] = await node.to_graphql(
                        db=db,
                        fields=self.params.fields,
                    )

        # Build results in same order as keys
        results: list[dict[str, Any] | None] = []
        for key in keys:
            if key == SYSTEM_USER_ID:
                results.append(self._build_system_account_response(self.params.fields))
            elif key in accounts_by_id:
                results.append(accounts_by_id[key])
            else:
                # Account not found - return placeholder
                results.append(self._build_unknown_account_response(key, self.params.fields))

        return results
