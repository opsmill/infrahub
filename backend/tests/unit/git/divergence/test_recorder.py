from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from infrahub.git.divergence.models import RefClassification, RefDivergence, RewriteRecord
from infrahub.git.divergence.recorder import HistoryRewriteRecorder
from tests.adapters.repository_record_store import InMemoryRepositoryRecordStore, WrittenRecord
from tests.unit.git.divergence.conftest import IMPORTED, REMOTE

REPOSITORY_ID = "repository-id"
REWRITTEN_AGAIN = "c" * 40
REWRITTEN_AT = datetime(2026, 10, 6, 9, 30, tzinfo=UTC)


def divergence(
    classification: RefClassification,
    imported: str | None = IMPORTED,
    remote: str | None = REMOTE,
) -> RefDivergence:
    return RefDivergence(
        branch_name="feature",
        infrahub_branch_name="feature",
        imported_commit=imported,
        remote_head=remote,
        classification=classification,
    )


def recorder(store: InMemoryRepositoryRecordStore) -> HistoryRewriteRecorder:
    return HistoryRewriteRecorder(store=store, clock=lambda: REWRITTEN_AT)


async def test_a_rewrite_records_both_commits_on_the_branch_it_names() -> None:
    store = InMemoryRepositoryRecordStore()

    await recorder(store).record(
        repository_id=REPOSITORY_ID, divergence=divergence(classification=RefClassification.REWRITE)
    )

    assert store.written == [
        WrittenRecord(
            repository_id=REPOSITORY_ID,
            infrahub_branch_name="feature",
            record=RewriteRecord(previous_commit=IMPORTED, commit=REMOTE, rewritten_at=REWRITTEN_AT, rewrite_count=1),
        )
    ]


async def test_a_rewrite_replaces_the_previous_record_and_adds_one_to_its_count() -> None:
    store = InMemoryRepositoryRecordStore()

    await recorder(store).record(
        repository_id=REPOSITORY_ID, divergence=divergence(classification=RefClassification.REWRITE)
    )
    await recorder(store).record(
        repository_id=REPOSITORY_ID,
        divergence=divergence(classification=RefClassification.REWRITE, imported=REMOTE, remote=REWRITTEN_AGAIN),
    )

    assert store.written[-1].record == RewriteRecord(
        previous_commit=REMOTE, commit=REWRITTEN_AGAIN, rewritten_at=REWRITTEN_AT, rewrite_count=2
    )


async def test_a_rewrite_counts_on_from_the_count_the_branch_reads() -> None:
    store = InMemoryRepositoryRecordStore(counts={(REPOSITORY_ID, "feature"): 3, (REPOSITORY_ID, "main"): 7})

    await recorder(store).record(
        repository_id=REPOSITORY_ID, divergence=divergence(classification=RefClassification.REWRITE)
    )

    assert [written.record.rewrite_count for written in store.written] == [4]
    assert store.counts == {(REPOSITORY_ID, "feature"): 4, (REPOSITORY_ID, "main"): 7}


@dataclass
class NotARewriteTestCase:
    name: str
    divergence: RefDivergence


NOT_A_REWRITE_TEST_CASES: list[NotARewriteTestCase] = [
    NotARewriteTestCase(
        name="retarget_whose_old_commit_the_remote_dropped",
        divergence=divergence(classification=RefClassification.RETARGET),
    ),
    NotARewriteTestCase(name="fast_forward", divergence=divergence(classification=RefClassification.FAST_FORWARD)),
    NotARewriteTestCase(
        name="ref_gone_from_the_remote",
        divergence=divergence(classification=RefClassification.REMOTE_ABSENT, remote=None),
    ),
    NotARewriteTestCase(
        name="unchanged", divergence=divergence(classification=RefClassification.UNCHANGED, remote=IMPORTED)
    ),
]


@pytest.mark.parametrize("test_case", [pytest.param(tc, id=tc.name) for tc in NOT_A_REWRITE_TEST_CASES])
async def test_only_a_rewrite_is_recorded(test_case: NotARewriteTestCase) -> None:
    store = InMemoryRepositoryRecordStore(counts={(REPOSITORY_ID, "feature"): 1})

    await recorder(store).record(repository_id=REPOSITORY_ID, divergence=test_case.divergence)

    assert store.written == []
    assert store.counts == {(REPOSITORY_ID, "feature"): 1}
