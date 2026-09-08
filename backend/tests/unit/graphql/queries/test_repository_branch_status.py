from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from graphene import DateTime

from infrahub.core.branch.models import Branch
from infrahub.core.constants import InfrahubKind, RepositoryInternalStatus, RepositorySyncStatus
from infrahub.core.query.repository import RepositoryBranchAttributeValue
from infrahub.core.repository_branch_status.models import RepositoryBranchAttributes
from infrahub.core.schema import SchemaRoot, core_models
from infrahub.exceptions import ValidationError
from infrahub.graphql.queries.repository_branch_status.kind_dispatch import policy_for_kind
from infrahub.graphql.queries.repository_branch_status.paging import (
    RepositoryBranchStatusRow,
    apply_value_filters,
    order_rows,
    page_rows,
)
from infrahub.graphql.queries.repository_branch_status.payload import build_attribute_payload
from infrahub.graphql.queries.repository_branch_status.stub import (
    PLACEHOLDER_UPDATED_AT,
    fabricate_attribute_values,
)

if TYPE_CHECKING:
    from infrahub.core.schema.attribute_schema import AttributeSchema

REPOSITORY_ID = "9c2a1e2c-0000-4000-8000-000000000001"


def _generic_repository_attribute(name: str) -> AttributeSchema:
    """Return the real attribute schema of the repository generic, without touching the database."""
    schema_root = SchemaRoot(**core_models)
    generic = next(item for item in schema_root.generics if item.kind == InfrahubKind.GENERICREPOSITORY)
    return generic.get_attribute(name=name)


def _value(
    attribute_name: str,
    value: str | None,
    branch_name: str = "branch-1",
    own_value: bool = True,
    updated_at: str | None = "2026-01-02T03:04:05.000000Z",
) -> RepositoryBranchAttributeValue:
    return RepositoryBranchAttributeValue(
        repository_id=REPOSITORY_ID,
        branch_name=branch_name,
        attribute_name=attribute_name,
        attribute_id=f"{branch_name}-{attribute_name}",
        value=value,
        own_value=own_value,
        updated_at=updated_at,
    )


def _branch(name: str, is_default: bool = False) -> Branch:
    return Branch(name=name, is_default=is_default)


def _row(
    *,
    branch_name: str,
    sync_status: str | None = None,
    internal_status: str | None = None,
    is_default: bool = False,
) -> RepositoryBranchStatusRow:
    values: dict[str, RepositoryBranchAttributeValue] = {}
    if sync_status is not None:
        values["sync_status"] = _value(attribute_name="sync_status", value=sync_status, branch_name=branch_name)
    if internal_status is not None:
        values["internal_status"] = _value(
            attribute_name="internal_status", value=internal_status, branch_name=branch_name
        )
    return RepositoryBranchStatusRow(branch=_branch(name=branch_name, is_default=is_default), values=values)


def _commit_row(
    *,
    branch_name: str,
    commit: str,
    own_value: bool,
    sync_status: str | None = None,
) -> RepositoryBranchStatusRow:
    row = _row(branch_name=branch_name, sync_status=sync_status)
    values = dict(row.values)
    values["commit"] = _value(attribute_name="commit", value=commit, branch_name=branch_name, own_value=own_value)
    return RepositoryBranchStatusRow(branch=row.branch, values=values)


class TestApplyValueFilters:
    def test_no_constraint_keeps_every_row_in_order(self) -> None:
        rows = [
            _row(branch_name="b-2", sync_status=RepositorySyncStatus.IN_SYNC.value),
            _row(branch_name="b-1", sync_status=RepositorySyncStatus.SYNCING.value),
        ]

        kept = apply_value_filters(rows=rows, sync_status=None, internal_status=None, own_values_only=False)

        assert [row.branch.name for row in kept] == ["b-2", "b-1"]

    def test_sync_status_keeps_only_matching_rows(self) -> None:
        rows = [
            _row(branch_name="b-1", sync_status=RepositorySyncStatus.IN_SYNC.value),
            _row(branch_name="b-2", sync_status=RepositorySyncStatus.ERROR_IMPORT.value),
            _row(branch_name="b-3", sync_status=RepositorySyncStatus.ERROR_IMPORT.value),
            _row(branch_name="b-4"),
        ]

        kept = apply_value_filters(
            rows=rows,
            sync_status=RepositorySyncStatus.ERROR_IMPORT.value,
            internal_status=None,
            own_values_only=False,
        )

        assert [row.branch.name for row in kept] == ["b-2", "b-3"]

    def test_internal_status_keeps_only_matching_rows(self) -> None:
        rows = [
            _row(branch_name="b-1", internal_status=RepositoryInternalStatus.ACTIVE.value),
            _row(branch_name="b-2", internal_status=RepositoryInternalStatus.INACTIVE.value),
        ]

        kept = apply_value_filters(
            rows=rows,
            sync_status=None,
            internal_status=RepositoryInternalStatus.ACTIVE.value,
            own_values_only=False,
        )

        assert [row.branch.name for row in kept] == ["b-1"]

    def test_both_value_filters_combine(self) -> None:
        rows = [
            _row(
                branch_name="b-1",
                sync_status=RepositorySyncStatus.IN_SYNC.value,
                internal_status=RepositoryInternalStatus.ACTIVE.value,
            ),
            _row(
                branch_name="b-2",
                sync_status=RepositorySyncStatus.IN_SYNC.value,
                internal_status=RepositoryInternalStatus.INACTIVE.value,
            ),
        ]

        kept = apply_value_filters(
            rows=rows,
            sync_status=RepositorySyncStatus.IN_SYNC.value,
            internal_status=RepositoryInternalStatus.ACTIVE.value,
            own_values_only=False,
        )

        assert [row.branch.name for row in kept] == ["b-1"]

    def test_own_values_only_anchors_on_the_commit_value(self) -> None:
        rows = [
            _commit_row(branch_name="own", commit="aaa", own_value=True),
            _commit_row(branch_name="inherited", commit="aaa", own_value=False),
            _row(branch_name="no-commit-row"),
        ]

        kept = apply_value_filters(rows=rows, sync_status=None, internal_status=None, own_values_only=True)

        assert [row.branch.name for row in kept] == ["own"]

    def test_own_values_only_ignores_the_other_selected_attributes(self) -> None:
        """The filter reads `commit` even when the caller selected a different attribute."""
        commit_only = [
            _commit_row(branch_name="own", commit="aaa", own_value=True),
            _commit_row(branch_name="inherited", commit="aaa", own_value=False),
        ]
        with_sync_status = [
            _commit_row(
                branch_name="own",
                commit="aaa",
                own_value=True,
                sync_status=RepositorySyncStatus.IN_SYNC.value,
            ),
            _commit_row(
                branch_name="inherited",
                commit="aaa",
                own_value=False,
                sync_status=RepositorySyncStatus.IN_SYNC.value,
            ),
        ]

        kept_commit_only = apply_value_filters(
            rows=commit_only, sync_status=None, internal_status=None, own_values_only=True
        )
        kept_with_sync_status = apply_value_filters(
            rows=with_sync_status, sync_status=None, internal_status=None, own_values_only=True
        )

        assert [row.branch.name for row in kept_commit_only] == ["own"]
        assert [row.branch.name for row in kept_with_sync_status] == ["own"]


class TestOrderRows:
    def test_default_branch_first_then_name_ascending(self) -> None:
        rows = [
            _row(branch_name="zulu"),
            _row(branch_name="alpha"),
            _row(branch_name="main", is_default=True),
            _row(branch_name="mike"),
        ]

        ordered = order_rows(rows=rows)

        assert [row.branch.name for row in ordered] == ["main", "alpha", "mike", "zulu"]

    def test_no_default_branch_orders_by_name(self) -> None:
        rows = [_row(branch_name="zulu"), _row(branch_name="alpha")]

        ordered = order_rows(rows=rows)

        assert [row.branch.name for row in ordered] == ["alpha", "zulu"]


class TestPageRows:
    rows = [_row(branch_name=f"b-{index}") for index in range(5)]

    def test_first_page(self) -> None:
        assert [row.branch.name for row in page_rows(rows=self.rows, offset=0, limit=2)] == ["b-0", "b-1"]

    def test_page_shorter_than_the_limit_at_the_tail(self) -> None:
        assert [row.branch.name for row in page_rows(rows=self.rows, offset=4, limit=40)] == ["b-4"]

    def test_offset_at_the_end_returns_nothing(self) -> None:
        assert page_rows(rows=self.rows, offset=5, limit=40) == []

    def test_offset_beyond_the_end_returns_nothing(self) -> None:
        assert page_rows(rows=self.rows, offset=500, limit=40) == []

    def test_limit_larger_than_the_row_count_returns_every_row(self) -> None:
        assert len(page_rows(rows=self.rows, offset=0, limit=1000)) == 5


class TestBuildAttributePayload:
    def test_none_value_yields_no_payload(self) -> None:
        assert (
            build_attribute_payload(value=None, attribute_schema=_generic_repository_attribute(name="commit")) is None
        )

    def test_text_attribute_payload(self) -> None:
        payload = build_attribute_payload(
            value=_value(attribute_name="commit", value="abc123"),
            attribute_schema=_generic_repository_attribute(name="commit"),
        )

        assert payload == {
            "id": "branch-1-commit",
            "value": "abc123",
            "updated_at": datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
            "is_default": None,
            "is_protected": None,
            "is_from_profile": None,
            "permissions": None,
            "source": None,
            "owner": None,
        }

    def test_updated_at_is_a_datetime_the_graphql_type_accepts(self) -> None:
        payload = build_attribute_payload(
            value=_value(attribute_name="commit", value="abc123"),
            attribute_schema=_generic_repository_attribute(name="commit"),
        )

        assert payload is not None
        assert DateTime.serialize(payload["updated_at"]) == "2026-01-02T03:04:05+00:00"

    def test_absent_updated_at_yields_none(self) -> None:
        payload = build_attribute_payload(
            value=_value(attribute_name="commit", value="abc123", updated_at=None),
            attribute_schema=_generic_repository_attribute(name="commit"),
        )

        assert payload is not None
        assert payload["updated_at"] is None

    def test_dropdown_payload_carries_the_schema_label_and_colour(self) -> None:
        payload = build_attribute_payload(
            value=_value(attribute_name="sync_status", value=RepositorySyncStatus.IN_SYNC.value),
            attribute_schema=_generic_repository_attribute(name="sync_status"),
        )

        assert payload is not None
        assert payload["value"] == "in-sync"
        assert payload["label"] == "In Sync"
        assert payload["color"] == "#60a5fa"
        assert payload["description"] == "The repository is syncing correctly"

    def test_dropdown_value_absent_from_the_choices_yields_null_labels(self) -> None:
        payload = build_attribute_payload(
            value=_value(attribute_name="sync_status", value="not-a-choice"),
            attribute_schema=_generic_repository_attribute(name="sync_status"),
        )

        assert payload is not None
        assert payload["value"] == "not-a-choice"
        assert payload["label"] is None
        assert payload["color"] is None
        assert payload["description"] is None

    def test_dropdown_with_a_null_stored_value_yields_null_labels(self) -> None:
        payload = build_attribute_payload(
            value=_value(attribute_name="sync_status", value=None),
            attribute_schema=_generic_repository_attribute(name="sync_status"),
        )

        assert payload is not None
        assert payload["value"] is None
        assert payload["label"] is None


class TestPolicyForKind:
    def test_read_write_repository(self) -> None:
        policy = policy_for_kind(kind=InfrahubKind.REPOSITORY)

        assert policy.kind == InfrahubKind.REPOSITORY
        assert policy.sync_with_git_filter is True
        assert policy.attribute_names == frozenset({"commit", "sync_status", "internal_status"})
        assert policy.permission_name == "Repository"

    def test_read_only_repository(self) -> None:
        policy = policy_for_kind(kind=InfrahubKind.READONLYREPOSITORY)

        assert policy.kind == InfrahubKind.READONLYREPOSITORY
        assert policy.sync_with_git_filter is None
        assert policy.attribute_names == frozenset({"commit", "sync_status", "internal_status", "ref"})
        assert policy.permission_name == "ReadOnlyRepository"

    def test_unsupported_kind_names_the_kind(self) -> None:
        with pytest.raises(
            ValidationError,
            match=(r"^Repository kind 'CoreGenericRepository' is not supported by the repository branch status query$"),
        ):
            policy_for_kind(kind=InfrahubKind.GENERICREPOSITORY)


class TestFabricateAttributeValues:
    attribute_names = frozenset({"commit", "sync_status", "internal_status", "ref"})
    twelve_names = tuple(f"branch-{index:02d}" for index in range(1, 13))

    def _values_by_name(self, branch_name: str, is_default_branch: bool = False) -> dict[str, str | None]:
        return {
            value.attribute_name: value.value
            for value in fabricate_attribute_values(
                repository_id=REPOSITORY_ID,
                branch_name=branch_name,
                attribute_names=self.attribute_names,
                is_default_branch=is_default_branch,
            )
        }

    def test_identical_arguments_yield_identical_values(self) -> None:
        first = fabricate_attribute_values(
            repository_id=REPOSITORY_ID,
            branch_name="branch-01",
            attribute_names=self.attribute_names,
            is_default_branch=False,
        )
        second = fabricate_attribute_values(
            repository_id=REPOSITORY_ID,
            branch_name="branch-01",
            attribute_names=self.attribute_names,
            is_default_branch=False,
        )

        assert first == second

    def test_every_requested_attribute_is_served(self) -> None:
        values = self._values_by_name(branch_name="branch-01")

        assert set(values) == self.attribute_names
        assert values["ref"] == "main"
        assert all(
            value.updated_at == PLACEHOLDER_UPDATED_AT
            for value in fabricate_attribute_values(
                repository_id=REPOSITORY_ID,
                branch_name="branch-01",
                attribute_names=self.attribute_names,
                is_default_branch=False,
            )
        )

    def test_unknown_attribute_names_are_skipped(self) -> None:
        values = fabricate_attribute_values(
            repository_id=REPOSITORY_ID,
            branch_name="branch-01",
            attribute_names={"commit", "operational_status"},
            is_default_branch=False,
        )

        assert [value.attribute_name for value in values] == ["commit"]

    def test_every_sync_status_choice_appears_across_twelve_names(self) -> None:
        served = {self._values_by_name(branch_name=name)["sync_status"] for name in self.twelve_names}

        assert served == {status.value for status in RepositorySyncStatus}

    def test_internal_status_follows_the_default_branch_flag(self) -> None:
        assert (
            self._values_by_name(branch_name="branch-01", is_default_branch=True)["internal_status"]
            == RepositoryInternalStatus.ACTIVE.value
        )
        assert (
            self._values_by_name(branch_name="branch-01", is_default_branch=False)["internal_status"]
            == RepositoryInternalStatus.INACTIVE.value
        )

    def test_the_default_branch_always_holds_its_own_value(self) -> None:
        values = fabricate_attribute_values(
            repository_id=REPOSITORY_ID,
            branch_name="branch-02",
            attribute_names={"commit"},
            is_default_branch=True,
        )

        assert [value.own_value for value in values] == [True]

    def test_own_value_varies_across_non_default_branches(self) -> None:
        own_values = {
            name: fabricate_attribute_values(
                repository_id=REPOSITORY_ID,
                branch_name=name,
                attribute_names={"commit"},
                is_default_branch=False,
            )[0].own_value
            for name in self.twelve_names
        }

        assert set(own_values.values()) == {True, False}


class TestRepositoryBranchAttributes:
    def test_get_returns_the_matching_value(self) -> None:
        value = _value(attribute_name="commit", value="abc123", branch_name="b-1")
        attributes = RepositoryBranchAttributes.from_values(values=[value])

        assert attributes.get(repository_id=REPOSITORY_ID, branch_name="b-1", attribute_name="commit") is value

    def test_get_miss_returns_none(self) -> None:
        attributes = RepositoryBranchAttributes.from_values(
            values=[_value(attribute_name="commit", value="abc123", branch_name="b-1")]
        )

        assert attributes.get(repository_id=REPOSITORY_ID, branch_name="b-2", attribute_name="commit") is None
        assert attributes.get(repository_id=REPOSITORY_ID, branch_name="b-1", attribute_name="ref") is None
        assert attributes.get(repository_id="other", branch_name="b-1", attribute_name="commit") is None

    def test_for_branch_returns_every_attribute_of_that_branch(self) -> None:
        attributes = RepositoryBranchAttributes.from_values(
            values=[
                _value(attribute_name="commit", value="abc123", branch_name="b-1"),
                _value(attribute_name="ref", value="main", branch_name="b-1"),
                _value(attribute_name="commit", value="def456", branch_name="b-2"),
            ]
        )

        assert set(attributes.for_branch(repository_id=REPOSITORY_ID, branch_name="b-1")) == {"commit", "ref"}
        assert attributes.for_branch(repository_id=REPOSITORY_ID, branch_name="unknown") == {}

    def test_duplicate_triple_raises(self) -> None:
        values = [
            _value(attribute_name="commit", value="abc123", branch_name="b-1"),
            _value(attribute_name="commit", value="def456", branch_name="b-1"),
        ]

        with pytest.raises(
            ValueError,
            match=(
                rf"^Duplicate attribute value for repository '{REPOSITORY_ID}', "
                r"branch 'b-1', attribute 'commit'$"
            ),
        ):
            RepositoryBranchAttributes.from_values(values=values)
