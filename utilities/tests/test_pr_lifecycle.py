from __future__ import annotations

# Ruff's pytest recommendations conflict with this standalone stdlib unittest suite.
# ruff: noqa: PT009, PT027
import contextlib
import io
import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Self
from unittest.mock import patch

from utilities.pr_lifecycle import (
    DASHBOARD_MARKER,
    TRUSTED_BOT,
    Aggregate,
    CacheRecord,
    FeedItem,
    GitHubClient,
    IncompleteDataError,
    Intent,
    JsonValue,
    Ledger,
    Receipt,
    Snapshot,
    collect_snapshot,
    continuation,
    decode_ledger,
    discover_dashboard,
    encode_ledger,
    finalize_receipt,
    main,
    observe,
    observe_activity,
    pages,
    prune_ledger,
    read_cache,
    recover_receipt,
    stage_intent,
    verify_candidates,
    verify_generation,
)

if TYPE_CHECKING:
    from urllib.request import Request


class RecordingTransport:
    def __init__(self, *, identity: JsonValue = None) -> None:
        self.paths: list[str] = []
        self.identity = identity

    def get_json(self, *, path: str) -> JsonValue:
        self.paths.append(path)
        return self.identity

    def query(self, *, number: int) -> JsonValue:
        raise IncompleteDataError(f"No GraphQL fixture for {number}")


def fixed_clock() -> datetime:
    return datetime(2026, 9, 28, 12, tzinfo=UTC)


class TestCliSkeleton(unittest.TestCase):
    def test_observe_default_reports_incomplete_without_writes(self) -> None:
        transport = RecordingTransport(identity={"full_name": "opsmill/infrahub"})
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "report.json"
            result = main(
                ["--repository", "opsmill/infrahub", "--report", str(report_path)],
                transport=transport,
                clock=fixed_clock,
            )
            report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(result, 1)
        self.assertEqual(transport.paths[0], "/repos/opsmill/infrahub")
        self.assertEqual(
            report,
            {
                "version": 1,
                "repository": "opsmill/infrahub",
                "mode": "observe",
                "observed_at": "2026-09-28T12:00:00+00:00",
                "complete": False,
                "closure_ready": False,
                "errors": ["Expected JSON array"],
                "inventory": [],
                "excluded_bots": [],
                "inventory_count": 0,
                "evaluated_count": 0,
                "requests": 2,
            },
        )

    def test_repository_guard_precedes_transport(self) -> None:
        transport = RecordingTransport()
        with self.assertRaisesRegex(ValueError, "Repository must be opsmill/infrahub"):
            observe(repository="other/repository", transport=transport, clock=fixed_clock)
        self.assertEqual(transport.paths, [])

    def test_mismatched_server_identity_is_rejected(self) -> None:
        transport = RecordingTransport(identity={"full_name": "other/repository"})
        with self.assertRaisesRegex(ValueError, "GitHub repository identity does not match"):
            observe(repository="opsmill/infrahub", transport=transport, clock=fixed_clock)
        self.assertEqual(transport.paths[0], "/repos/opsmill/infrahub")

    def test_apply_mode_is_rejected_before_transport(self) -> None:
        transport = RecordingTransport()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main(["--repository", "opsmill/infrahub", "--mode", "apply"], transport=transport)
        self.assertEqual(raised.exception.code, 2)
        self.assertEqual(transport.paths, [])

    def test_naive_clock_is_rejected_before_transport(self) -> None:
        transport = RecordingTransport()
        with self.assertRaisesRegex(ValueError, "Clock must return a timezone-aware timestamp"):
            observe(
                repository="opsmill/infrahub",
                transport=transport,
                clock=lambda: fixed_clock().replace(tzinfo=None),
            )
        self.assertEqual(transport.paths, [])

    def test_fixture_files_are_valid_json(self) -> None:
        fixture_dir = Path(__file__).parent / "fixtures" / "pr_lifecycle"
        fixtures = sorted(fixture_dir.glob("*.json"))
        self.assertEqual([path.name for path in fixtures], ["activity.json", "mergeability.json", "reviews.json"])
        for path in fixtures:
            with self.subTest(fixture=path.name):
                self.assertIsInstance(json.loads(path.read_text(encoding="utf-8")), dict)


OLD = "2026-07-01T12:00:00+00:00"
NOW = "2026-09-28T12:00:00+00:00"


def snapshot(**changes: object) -> Snapshot:
    value = Snapshot(
        number=1,
        node_id="PR_1",
        title="Example",
        url="https://github.com/opsmill/infrahub/pull/1",
        author="alice",
        author_type="User",
        state="open",
        draft=False,
        updated_at=OLD,
        head="abc",
        base="stable",
        labels=(),
        assignees=(),
        requested_users=(),
        requested_teams=(),
        reviews=(),
        checks=(),
        aggregate=Aggregate(head="abc", mergeable="MERGEABLE", merge_state="CLEAN", review_decision=None),
        feed=(),
        fingerprint="original",
        observed_at=NOW,
    )
    return replace(value, **changes)


class FixtureTransport:
    def __init__(self, *, responses: dict[str, JsonValue], graphql: JsonValue = None) -> None:
        self.responses = responses
        self.graphql = graphql
        self.paths: list[str] = []
        self.queries: list[int] = []

    def get_json(self, *, path: str) -> JsonValue:
        self.paths.append(path)
        if path not in self.responses:
            raise IncompleteDataError("Missing fixture response")
        return self.responses[path]

    def query(self, *, number: int) -> JsonValue:
        self.queries.append(number)
        return self.graphql


class TestActivity(unittest.TestCase):
    def test_inactivity_survives_weekly_owned_comment_and_recovery(self) -> None:
        initial = snapshot()
        entry = observe_activity(snapshot=initial, previous=None)
        item = FeedItem(
            identity="comment:9", actor=TRUSTED_BOT, kind="comment", at=NOW, content_hash="notice-with-operation-id"
        )
        intent = Intent(operation="weekly-1", kind="comment", content_hash=item.content_hash, prior_hash="original")
        recovered = recover_receipt(intent=intent, feed=(item,))
        self.assertIsNotNone(recovered)
        if recovered is None:
            self.fail("Expected a verified receipt")
        persisted = replace(entry, receipts=(recovered,))
        restored = decode_ledger(body=encode_ledger(ledger=Ledger(entries=(persisted,)))).entries[0]
        observed = observe_activity(snapshot=replace(initial, updated_at=NOW, feed=(item,)), previous=restored)
        self.assertEqual(observed.activity_at, OLD)
        repeated = observe_activity(snapshot=replace(initial, updated_at=NOW, feed=(item,)), previous=observed)
        self.assertEqual(repeated.activity_at, OLD)

    def test_human_comment_cancels_warning(self) -> None:
        entry = replace(observe_activity(snapshot=snapshot(), previous=None), warning="cycle-1")
        item = FeedItem(identity="comment:10", actor="alice", kind="comment", at=NOW, content_hash="human")
        result = observe_activity(snapshot=snapshot(updated_at=NOW, feed=(item,)), previous=entry)
        self.assertEqual((result.activity_at, result.warning), (NOW, None))

    def test_other_bot_and_edited_owned_comment_reset(self) -> None:
        owned = Receipt(
            operation="op", identity="comment:10", actor=TRUSTED_BOT, kind="comment", at=OLD, content_hash="original"
        )
        entry = replace(observe_activity(snapshot=snapshot(), previous=None), receipts=(owned,), warning="cycle")
        for actor in ("another[bot]", TRUSTED_BOT):
            with self.subTest(actor=actor):
                item = FeedItem(identity="comment:10", actor=actor, kind="comment", at=NOW, content_hash="edited")
                result = observe_activity(snapshot=snapshot(updated_at=NOW, feed=(item,)), previous=entry)
                self.assertEqual((result.activity_at, result.warning), (NOW, None))

    def test_human_reserved_label_and_forged_marker_count_as_activity(self) -> None:
        entry = replace(observe_activity(snapshot=snapshot(), previous=None), warning="cycle")
        for kind in ("labeled", "comment"):
            with self.subTest(kind=kind):
                item = FeedItem(
                    identity="event:10", actor="alice", kind=kind, at=NOW, content_hash="forged-operation-marker"
                )
                result = observe_activity(snapshot=snapshot(updated_at=NOW, feed=(item,)), previous=entry)
                self.assertEqual((result.activity_at, result.warning), (NOW, None))

    def test_head_change_uses_observation_not_commit_date(self) -> None:
        entry = observe_activity(snapshot=snapshot(), previous=None)
        result = observe_activity(snapshot=snapshot(head="new-head"), previous=entry)
        self.assertEqual(result.activity_at, NOW)

    def test_unknown_raw_or_fingerprint_change_resets(self) -> None:
        entry = replace(observe_activity(snapshot=snapshot(), previous=None), warning="cycle")
        for updated in (snapshot(updated_at=NOW), snapshot(fingerprint="changed"), snapshot(labels=("keep-open",))):
            with self.subTest(updated=updated):
                result = observe_activity(snapshot=updated, previous=entry)
                self.assertEqual((result.activity_at, result.warning), (NOW, None))

    def test_reopened_clears_old_warning_and_notice(self) -> None:
        entry = replace(observe_activity(snapshot=snapshot(), previous=None), warning="cycle", last_notice_at=OLD)
        reopened = "2026-09-27T14:00:00+00:00"
        item = FeedItem(identity="event:11", actor="alice", kind="reopened", at=reopened, content_hash="reopened")
        result = observe_activity(snapshot=snapshot(updated_at=reopened, feed=(item,)), previous=entry)
        self.assertEqual((result.activity_at, result.warning, result.last_notice_at), (reopened, None, None))


class TestLedger(unittest.TestCase):
    def test_failed_finalization_preserves_pending_intent(self) -> None:
        original = observe_activity(snapshot=snapshot(), previous=None)
        intent = Intent(operation="op", kind="comment", content_hash="exact", prior_hash=original.fingerprint)
        staged = stage_intent(entry=original, intent=intent)
        wrong = Receipt(
            operation="wrong", identity="comment:1", actor=TRUSTED_BOT, kind="comment", at=NOW, content_hash="exact"
        )
        with self.assertRaisesRegex(IncompleteDataError, "does not match"):
            finalize_receipt(entry=staged, receipt=wrong)
        self.assertEqual(staged.pending, intent)
        finalized = finalize_receipt(entry=staged, receipt=replace(wrong, operation="op"))
        self.assertEqual((finalized.pending, len(finalized.receipts)), (None, 1))
        with self.assertRaisesRegex(IncompleteDataError, "baseline conflict"):
            stage_intent(entry=original, intent=replace(intent, prior_hash="other"))

    def test_roundtrip_and_guard(self) -> None:
        ledger = Ledger(generation=2, entries=(observe_activity(snapshot=snapshot(), previous=None),))
        self.assertEqual(decode_ledger(body=encode_ledger(ledger=ledger)), ledger)
        with self.assertRaisesRegex(IncompleteDataError, "exceeds 60000"):
            encode_ledger(ledger=ledger, visible="x" * 60000)

    def test_corrupt_unsupported_missing_state_fails(self) -> None:
        for body in ("", "<!-- infrahub-pr-lifecycle:state:v1 invalid -->"):
            with self.subTest(body=body), self.assertRaises(IncompleteDataError):
                decode_ledger(body=body)
        body = encode_ledger(ledger=Ledger())
        with self.assertRaisesRegex(IncompleteDataError, "Missing or ambiguous"):
            decode_ledger(body=body.replace("state:v1", "state:v99"))

    def test_generation_and_unversioned_human_edit_conflict(self) -> None:
        original = encode_ledger(ledger=Ledger(generation=1))
        for changed in (encode_ledger(ledger=Ledger(generation=2)), "human edit" + original):
            with self.subTest(changed=changed), self.assertRaisesRegex(IncompleteDataError, "conflict"):
                verify_generation(expected_body=original, current_body=changed)

    def test_recovery_never_trusts_forged_author_or_edited_content(self) -> None:
        intent = Intent(operation="op", kind="comment", content_hash="exact", prior_hash="prior")
        for item in (
            FeedItem(identity="comment:1", actor="human", kind="comment", at=NOW, content_hash="exact"),
            FeedItem(identity="comment:1", actor=TRUSTED_BOT, kind="comment", at=NOW, content_hash="edited"),
        ):
            with self.subTest(item=item):
                self.assertIsNone(recover_receipt(intent=intent, feed=(item,)))

    def test_ambiguous_post_receipt_is_not_retried_or_assumed(self) -> None:
        intent = Intent(operation="op", kind="comment", content_hash="exact", prior_hash="prior")
        item = FeedItem(identity="comment:1", actor=TRUSTED_BOT, kind="comment", at=NOW, content_hash="exact")
        with self.assertRaisesRegex(IncompleteDataError, "Ambiguous write"):
            recover_receipt(intent=intent, feed=(item, replace(item, identity="comment:2")))
        self.assertIsNone(recover_receipt(intent=intent, feed=()))

    def test_unresolved_intent_survives_retention(self) -> None:
        entry = observe_activity(snapshot=snapshot(), previous=None)
        intent = Intent(operation="op", kind="comment", content_hash="exact", prior_hash="prior")
        unresolved = replace(entry, pending=intent)
        for value, expected in ((entry, ()), (unresolved, (unresolved,))):
            result = prune_ledger(
                ledger=Ledger(entries=(value,)), confirmed_closed=frozenset({1}), gates_cleaned=frozenset({1})
            )
            self.assertEqual(result.entries, expected)
        self.assertEqual(
            prune_ledger(
                ledger=Ledger(entries=(entry,)), confirmed_closed=frozenset({1}), gates_cleaned=frozenset()
            ).entries,
            (entry,),
        )

    def test_dashboard_provenance_and_duplicates(self) -> None:
        path = "/repos/opsmill/infrahub/issues?state=all&creator=github-actions%5Bbot%5D&per_page=100&page=1"
        issue: dict[str, JsonValue] = {
            "id": 1,
            "number": 1,
            "body": DASHBOARD_MARKER,
            "user": {"login": TRUSTED_BOT, "type": "Bot"},
        }
        self.assertEqual(
            discover_dashboard(transport=FixtureTransport(responses={path: [issue]})), (1, DASHBOARD_MARKER)
        )
        with self.assertRaisesRegex(IncompleteDataError, "untrusted"):
            discover_dashboard(
                transport=FixtureTransport(responses={path: [{**issue, "user": {"login": "human", "type": "User"}}]})
            )
        with self.assertRaisesRegex(IncompleteDataError, "Multiple dashboards"):
            discover_dashboard(transport=FixtureTransport(responses={path: [issue, {**issue, "id": 2, "number": 2}]}))


class TestCollection(unittest.TestCase):
    def test_complete_pagination_and_duplicate_failure(self) -> None:
        first: list[JsonValue] = [{"id": number} for number in range(100)]
        transport = FixtureTransport(
            responses={"/list?per_page=100&page=1": first, "/list?per_page=100&page=2": [{"id": 100}]}
        )
        self.assertEqual(len(pages(transport=transport, path="/list")), 101)
        self.assertEqual(transport.paths, ["/list?per_page=100&page=1", "/list?per_page=100&page=2"])
        transport.responses["/list?per_page=100&page=2"] = [{"id": 0}]
        with self.assertRaisesRegex(IncompleteDataError, "Duplicate item"):
            pages(transport=transport, path="/list")

    def test_missing_page_fails_instead_of_partial_success(self) -> None:
        transport = FixtureTransport(responses={"/list?per_page=100&page=1": [{"id": number} for number in range(100)]})
        with self.assertRaisesRegex(IncompleteDataError, "Missing fixture"):
            pages(transport=transport, path="/list")

    def test_empty_inventory_succeeds_without_mutations(self) -> None:
        transport = FixtureTransport(
            responses={
                "/repos/opsmill/infrahub": {"full_name": "opsmill/infrahub"},
                "/rate_limit": {"resources": {"core": {"remaining": 1000}, "graphql": {"remaining": 1000}}},
                "/repos/opsmill/infrahub/issues?state=all&creator=github-actions%5Bbot%5D&per_page=100&page=1": [],
                "/repos/opsmill/infrahub/pulls?state=open&per_page=100&page=1": [],
            }
        )
        report = observe(repository="opsmill/infrahub", transport=transport, clock=fixed_clock)
        self.assertEqual((report.complete, report.closure_ready, report.inventory), (True, False, ()))
        self.assertEqual(transport.queries, [])


def collection_transport() -> FixtureTransport:
    root = "/repos/opsmill/infrahub"
    responses: dict[str, JsonValue] = {
        f"{root}/pulls/1": {
            "number": 1,
            "node_id": "PR_1",
            "title": "Example",
            "html_url": "https://github.com/opsmill/infrahub/pull/1",
            "body": "description",
            "user": {"login": "alice", "type": "User"},
            "draft": False,
            "state": "open",
            "updated_at": OLD,
            "created_at": OLD,
            "head": {"sha": "abc"},
            "base": {"ref": "stable"},
            "labels": [],
            "assignees": [],
        },
        f"{root}/pulls/1/requested_reviewers?per_page=100&page=1": {"users": [], "teams": []},
        f"{root}/commits/abc/check-runs?per_page=100&page=1": {"check_runs": [], "total_count": 0},
        f"{root}/commits/abc/statuses?per_page=100&page=1": [],
    }
    for path in ("issues/1/comments", "pulls/1/comments", "issues/1/timeline", "pulls/1/reviews"):
        responses[f"{root}/{path}?per_page=100&page=1"] = []
    return FixtureTransport(
        responses=responses,
        graphql={
            "data": {
                "repository": {
                    "pullRequest": {
                        "headRefOid": "abc",
                        "mergeable": "MERGEABLE",
                        "mergeStateStatus": "CLEAN",
                        "reviewDecision": None,
                    }
                }
            }
        },
    )


class TestSnapshotBoundary(unittest.TestCase):
    def test_complete_same_head_snapshot_accepts_explicit_null_review_rule(self) -> None:
        transport = collection_transport()
        result = collect_snapshot(transport=transport, number=1, now=fixed_clock())
        self.assertEqual(
            (result.number, result.head, result.aggregate.review_decision, result.feed), (1, "abc", None, ())
        )
        self.assertEqual(len(transport.paths), 8)
        self.assertEqual(transport.queries, [1])

    def test_missing_aggregate_error_or_head_mismatch_fails(self) -> None:
        cases: tuple[JsonValue, ...] = (
            {"errors": [{"message": "denied"}]},
            {
                "data": {
                    "repository": {
                        "pullRequest": {"headRefOid": "abc", "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN"}
                    }
                }
            },
            {
                "data": {
                    "repository": {
                        "pullRequest": {
                            "headRefOid": "old",
                            "mergeable": "MERGEABLE",
                            "mergeStateStatus": "CLEAN",
                            "reviewDecision": None,
                        }
                    }
                }
            },
        )
        for graphql in cases:
            with self.subTest(graphql=graphql):
                transport = collection_transport()
                transport.graphql = graphql
                with self.assertRaises(IncompleteDataError):
                    collect_snapshot(transport=transport, number=1, now=fixed_clock())

    def test_review_comments_and_timeline_are_collected(self) -> None:
        transport = collection_transport()
        transport.responses["/repos/opsmill/infrahub/pulls/1/comments?per_page=100&page=1"] = [
            {"id": 55, "user": {"login": "reviewer"}, "body": "change this", "updated_at": NOW}
        ]
        result = collect_snapshot(transport=transport, number=1, now=fixed_clock())
        self.assertEqual(
            tuple((item.identity, item.actor, item.at) for item in result.feed),
            (("review-comment:55", "reviewer", NOW),),
        )

    def test_unrelated_head_repository_metadata_is_not_activity(self) -> None:
        transport = collection_transport()
        before = collect_snapshot(transport=transport, number=1, now=fixed_clock())
        pr = transport.responses["/repos/opsmill/infrahub/pulls/1"]
        if not isinstance(pr, dict):
            self.fail("Expected PR fixture")
        pr["head"] = {"sha": "abc", "repo": {"updated_at": NOW}}
        after = collect_snapshot(transport=transport, number=1, now=fixed_clock())
        self.assertEqual(before.fingerprint, after.fingerprint)


class TestReliability(unittest.TestCase):
    def test_exact_cache_key_and_ref_metadata(self) -> None:
        path = "/repos/opsmill/infrahub/actions/caches?key=_state&ref=refs%2Fheads%2Fstable&per_page=100&page=1"
        record: dict[str, JsonValue] = {
            "id": 1,
            "key": "_state",
            "ref": "refs/heads/stable",
            "created_at": OLD,
            "last_accessed_at": NOW,
            "size_in_bytes": 100,
        }
        transport = FixtureTransport(
            responses={
                path: {
                    "actions_caches": [
                        record,
                        {**record, "id": 2, "key": "_state-other"},
                        {**record, "id": 3, "ref": "refs/heads/other"},
                    ],
                    "total_count": 3,
                }
            }
        )
        result = read_cache(transport=transport, ref="refs/heads/stable")
        self.assertEqual(result, CacheRecord(identity=1, created_at=OLD, last_accessed_at=NOW, size_in_bytes=100))
        transport.responses[path] = {"actions_caches": [record, {**record, "id": 2}], "total_count": 2}
        with self.assertRaisesRegex(IncompleteDataError, "Ambiguous"):
            read_cache(transport=transport, ref="refs/heads/stable")

    def test_independent_candidate_verification_rejects_unknown_state(self) -> None:
        root = "/repos/opsmill/infrahub/pulls"
        transport = FixtureTransport(
            responses={
                f"{root}/1": {"number": 1, "state": "closed"},
                f"{root}/2": {"number": 2, "state": "open"},
            }
        )
        self.assertEqual(verify_candidates(transport=transport, candidates=(1, 2)), (2,))
        transport.responses[f"{root}/2"] = {"number": 2, "state": "unknown"}
        with self.assertRaises(IncompleteDataError):
            verify_candidates(transport=transport, candidates=(1, 2))

    def test_continuation_requires_cache_replacement_or_semantic_progress(self) -> None:
        cache = CacheRecord(identity=1, created_at=OLD, last_accessed_at=OLD, size_in_bytes=10)
        for after in (cache, replace(cache, last_accessed_at=NOW)):
            with self.subTest(after=after), self.assertRaisesRegex(IncompleteDataError, "unchanged"):
                continuation(pass_number=1, before=cache, after=after, previous=(1, 2), remaining=(2,))
        self.assertTrue(
            continuation(
                pass_number=1, before=cache, after=replace(cache, identity=2), previous=(1, 2), remaining=(1, 2)
            )
        )
        self.assertTrue(continuation(pass_number=1, before=cache, after=None, previous=(1,), remaining=(1,)))
        self.assertFalse(continuation(pass_number=1, before=cache, after=None, previous=(1,), remaining=()))
        for pass_number in (2, 3):
            with self.subTest(pass_number=pass_number), self.assertRaises(IncompleteDataError):
                continuation(pass_number=pass_number, before=None, after=None, previous=(1,), remaining=(1,))

    def test_incomplete_observation_never_authorizes_closure(self) -> None:
        for missing in collection_transport().responses:
            with self.subTest(missing=missing):
                transport = observation_transport()
                del transport.responses[missing]
                report = observe(repository="opsmill/infrahub", transport=transport, clock=fixed_clock)
                self.assertFalse(report.complete)
                self.assertFalse(report.closure_ready)

    def test_current_and_larger_bot_backlogs_use_inventory_only(self) -> None:
        for count in (116, 574):
            with self.subTest(count=count):
                transport = observation_transport(count=count, bots=True)
                report = observe(repository="opsmill/infrahub", transport=transport, clock=fixed_clock)
                self.assertTrue(report.complete, report.errors)
                self.assertFalse(report.closure_ready)
                self.assertEqual(len(report.excluded_bots), count)
                self.assertEqual(report.evaluated_count, count)
                self.assertEqual(transport.queries, [])

    def test_insufficient_quota_stops_before_human_detail_reads(self) -> None:
        transport = observation_transport(count=574)
        report = observe(repository="opsmill/infrahub", transport=transport, clock=fixed_clock)
        self.assertFalse(report.complete)
        self.assertIn("quota", report.errors[0])
        self.assertEqual(transport.queries, [])
        self.assertNotIn("/repos/opsmill/infrahub/pulls/1", transport.paths)

    def test_budget_stops_before_partial_collection(self) -> None:
        report = observe(repository="opsmill/infrahub", transport=observation_transport(), clock=fixed_clock, budget=5)
        self.assertFalse(report.complete)
        self.assertFalse(report.closure_ready)
        self.assertIn("budget", report.errors[0])

    def test_complete_observe_has_no_write_transport_operations(self) -> None:
        transport = observation_transport()
        report = observe(repository="opsmill/infrahub", transport=transport, clock=fixed_clock)
        self.assertTrue(report.complete, report.errors)
        self.assertFalse(report.closure_ready)
        self.assertEqual(report.evaluated_count, 1)
        self.assertEqual(transport.queries, [1])

    def test_full_human_inventory_with_sufficient_quota(self) -> None:
        for count in (116, 574):
            with self.subTest(count=count):
                transport = observation_transport(count=count)
                transport.responses["/rate_limit"] = {
                    "resources": {
                        "core": {"remaining": 10000},
                        "graphql": {"remaining": 10000},
                    }
                }
                report = observe(repository="opsmill/infrahub", transport=transport, clock=fixed_clock, budget=10000)
                self.assertTrue(report.complete, report.errors)
                self.assertEqual(report.evaluated_count, count)
                self.assertEqual(len(transport.queries), count)

    def test_current_mixed_backlog_fits_github_token_quota(self) -> None:
        transport = observation_transport(count=116)
        page = transport.responses["/repos/opsmill/infrahub/pulls?state=open&per_page=100&page=1"]
        if not isinstance(page, list):
            self.fail("Expected inventory page")
        for item in page[:5]:
            if not isinstance(item, dict):
                self.fail("Expected PR")
            item["user"] = {"login": "dependabot[bot]", "type": "Bot"}
        report = observe(repository="opsmill/infrahub", transport=transport, clock=fixed_clock)
        self.assertTrue(report.complete, report.errors)
        self.assertEqual((report.evaluated_count, len(report.excluded_bots)), (116, 5))
        self.assertLess(len(transport.paths), 950)

    def test_http_transport_only_sends_get_and_fixed_graphql_query(self) -> None:
        requests: list[Request] = []

        class Response:
            def __init__(self) -> None:
                self.headers = {"X-RateLimit-Remaining": "999", "X-RateLimit-Resource": "core"}

            def __enter__(self) -> Self:
                return self

            def __exit__(self, *args: object) -> None:
                pass

            def read(self) -> bytes:
                return b"{}"

        def open_fixture(request: Request, **_kwargs: object) -> Response:
            requests.append(request)
            return Response()

        client = GitHubClient(token=TRUSTED_BOT)
        with patch("urllib.request.urlopen", side_effect=open_fixture):
            client.get_json(path="/repos/opsmill/infrahub/pulls/1")
            client.query(number=1)
        self.assertEqual([request.get_method() for request in requests], ["GET", "POST"])
        payload = requests[1].data
        if not isinstance(payload, bytes):
            self.fail("Expected GraphQL request payload")
        self.assertTrue(json.loads(payload)["query"].startswith("query("))
        with self.assertRaisesRegex(IncompleteDataError, "outside"):
            client.get_json(path="/repos/other/repo")

    def test_rate_buckets_and_actual_http_budget_are_independent(self) -> None:
        client = GitHubClient(token=TRUSTED_BOT, budget=1)
        client.account_headers(headers={"X-RateLimit-Remaining": "500", "X-RateLimit-Resource": "core"})
        client.account_headers(headers={"X-RateLimit-Remaining": "1000", "X-RateLimit-Resource": "graphql"})
        self.assertEqual(client.quotas, {"core": 500, "graphql": 1000})
        client.requests = 1
        with self.assertRaisesRegex(IncompleteDataError, "budget"):
            client.get_json(path="/rate_limit")
        client.requests = 0
        client.quotas["core"] = 50
        with self.assertRaisesRegex(IncompleteDataError, "quota"):
            client.get_json(path="/rate_limit")

    def test_workflow_has_only_trusted_observation(self) -> None:
        workflow = (Path(__file__).parents[2] / ".github/workflows/manage-stale-prs.yml").read_text()
        self.assertNotIn("workflow_dispatch:\n    inputs:", workflow)
        self.assertNotIn("write", workflow)
        self.assertIn("ref: stable", workflow)
        self.assertIn("--mode observe", workflow)
        self.assertNotIn("uses: actions/stale", workflow)
        self.assertIn("cancel-in-progress: false", workflow)


def observation_transport(*, count: int = 1, bots: bool = False) -> FixtureTransport:
    transport = collection_transport()
    root = "/repos/opsmill/infrahub"
    transport.responses[root] = {"full_name": "opsmill/infrahub"}
    transport.responses["/rate_limit"] = {
        "resources": {
            "core": {"remaining": 1000},
            "graphql": {"remaining": 1000},
        }
    }
    transport.responses[f"{root}/issues?state=all&creator=github-actions%5Bbot%5D&per_page=100&page=1"] = []
    if not bots:
        for number in range(2, count + 1):
            for path, original_value in collection_transport().responses.items():
                value = original_value
                replacement = path.replace("/1/", f"/{number}/")
                if path.endswith("/1"):
                    replacement = path[:-1] + str(number)
                    if not isinstance(value, dict):
                        raise AssertionError("Expected PR fixture")
                    value = {**value, "number": number, "node_id": f"PR_{number}"}
                transport.responses[replacement] = value
    items: list[JsonValue] = [
        {
            "id": number,
            "number": number,
            "user": {"login": "dependabot[bot]" if bots else "alice", "type": "Bot" if bots else "User"},
        }
        for number in range(1, count + 1)
    ]
    for page in range(count // 100 + 1):
        transport.responses[f"{root}/pulls?state=open&per_page=100&page={page + 1}"] = items[
            page * 100 : (page + 1) * 100
        ]
    return transport


if __name__ == "__main__":
    unittest.main()
