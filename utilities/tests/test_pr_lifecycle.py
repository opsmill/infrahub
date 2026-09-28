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
    Lifecycle,
    Mode,
    Receipt,
    Review,
    Snapshot,
    WarningCycle,
    activity_digest,
    apply_command,
    array,
    classify,
    closure_due,
    closure_exemptions,
    collect_snapshot,
    continuation,
    current_reviews,
    decode_ledger,
    digest,
    discover_dashboard,
    encode_ledger,
    feed_digest,
    finalize_receipt,
    main,
    next_notice,
    notice_body,
    object_value,
    observe,
    observe_activity,
    pages,
    prune_ledger,
    read_cache,
    reconcile_pending,
    recover_receipt,
    render_dashboard,
    stage_intent,
    string,
    validate_write,
    verify_candidates,
    verify_generation,
    warning_needed,
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
                "proposals": [],
                "bot_rows": [],
                "dashboard_preview": None,
                "proposed_counts": [
                    [kind, 0] for kind in ("ordinary", "warning", "cancel", "milestone-7", "milestone-1")
                ],
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
        entry = replace(
            observe_activity(snapshot=snapshot(), previous=None),
            warning=WarningCycle(cycle="cycle-1", delivered_at=OLD, deadline=NOW, initial_operation="initial"),
        )
        item = FeedItem(identity="comment:10", actor="alice", kind="comment", at=NOW, content_hash="human")
        result = observe_activity(snapshot=snapshot(updated_at=NOW, feed=(item,)), previous=entry)
        self.assertEqual((result.activity_at, result.warning), (NOW, None))

    def test_other_bot_and_edited_owned_comment_reset(self) -> None:
        owned = Receipt(
            operation="op", identity="comment:10", actor=TRUSTED_BOT, kind="comment", at=OLD, content_hash="original"
        )
        entry = replace(
            observe_activity(snapshot=snapshot(), previous=None),
            receipts=(owned,),
            warning=WarningCycle(cycle="cycle", delivered_at=OLD, deadline=NOW, initial_operation="initial"),
        )
        for actor in ("another[bot]", TRUSTED_BOT):
            with self.subTest(actor=actor):
                item = FeedItem(identity="comment:10", actor=actor, kind="comment", at=NOW, content_hash="edited")
                result = observe_activity(snapshot=snapshot(updated_at=NOW, feed=(item,)), previous=entry)
                self.assertEqual((result.activity_at, result.warning), (NOW, None))

    def test_human_reserved_label_and_forged_marker_count_as_activity(self) -> None:
        entry = replace(
            observe_activity(snapshot=snapshot(), previous=None),
            warning=WarningCycle(cycle="cycle", delivered_at=OLD, deadline=NOW, initial_operation="initial"),
        )
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
        entry = replace(
            observe_activity(snapshot=snapshot(), previous=None),
            warning=WarningCycle(cycle="cycle", delivered_at=OLD, deadline=NOW, initial_operation="initial"),
        )
        for updated in (snapshot(updated_at=NOW), snapshot(fingerprint="changed"), snapshot(labels=("keep-open",))):
            with self.subTest(updated=updated):
                result = observe_activity(snapshot=updated, previous=entry)
                self.assertEqual((result.activity_at, result.warning), (NOW, None))

    def test_reopened_clears_old_warning_and_notice(self) -> None:
        entry = replace(
            observe_activity(snapshot=snapshot(), previous=None),
            warning=WarningCycle(cycle="cycle", delivered_at=OLD, deadline=NOW, initial_operation="initial"),
            last_notice_at=OLD,
        )
        reopened = "2026-09-27T14:00:00+00:00"
        item = FeedItem(identity="event:11", actor="alice", kind="reopened", at=reopened, content_hash="reopened")
        result = observe_activity(snapshot=snapshot(updated_at=reopened, feed=(item,)), previous=entry)
        self.assertEqual((result.activity_at, result.warning, result.last_notice_at), (reopened, None, None))

    def test_delayed_reopen_observation_preserves_newer_activity(self) -> None:
        previous = observe_activity(snapshot=snapshot(), previous=None)
        reopened = FeedItem(identity="event:11", actor="alice", kind="reopened", at=OLD, content_hash="reopened")
        comment = FeedItem(identity="comment:12", actor="alice", kind="comment", at=NOW, content_hash="still active")
        for current in (
            snapshot(updated_at=NOW, feed=(reopened, comment)),
            snapshot(updated_at=OLD, head="new-head", feed=(reopened,)),
        ):
            with self.subTest(head=current.head, comments=len(current.feed)):
                result = observe_activity(snapshot=current, previous=previous)
                self.assertEqual(result.activity_at, NOW)
                self.assertFalse(warning_needed(snapshot=current, entry=result, now=fixed_clock()))


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
        for count, expected_complete in ((116, True), (574, False)):
            with self.subTest(count=count):
                transport = observation_transport(count=count)
                transport.responses["/rate_limit"] = {
                    "resources": {
                        "core": {"remaining": 10000},
                        "graphql": {"remaining": 10000},
                    }
                }
                report = observe(repository="opsmill/infrahub", transport=transport, clock=fixed_clock, budget=10000)
                self.assertEqual(report.complete, expected_complete)
                if not expected_complete:
                    self.assertEqual(report.errors, ("Dashboard exceeds 60000 characters",))
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
        observe_job, mutation_job = workflow.split("  mutate:", 1)
        self.assertNotIn("write", observe_job)
        self.assertIn("\n    if: false\n", mutation_job)
        self.assertEqual(mutation_job.count("uses: actions/stale@4391f3da665fdf50b6810c1a66712fb9ba21aa93"), 4)
        self.assertIn("if: always()", mutation_job)
        self.assertIn("ref: stable", workflow)
        self.assertIn("--mode observe", workflow)
        self.assertNotIn("uses: actions/stale", observe_job)
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
            "title": "Example bot PR",
            "user": {"login": "dependabot[bot]" if bots else "alice", "type": "Bot" if bots else "User"},
        }
        for number in range(1, count + 1)
    ]
    for page in range(count // 100 + 1):
        transport.responses[f"{root}/pulls?state=open&per_page=100&page={page + 1}"] = items[
            page * 100 : (page + 1) * 100
        ]
    return transport


class TestCleanupPolicy(unittest.TestCase):
    def test_partial_approval_and_comment_do_not_remove_exemption(self) -> None:

        approval = Review(identity=1, author="bob", state="APPROVED", submitted_at=OLD)
        comment = replace(approval, identity=2, state="COMMENTED", submitted_at=NOW)
        value = snapshot(reviews=(approval, comment), requested_users=("charlie",))
        self.assertEqual(current_reviews(snapshot=value), {"bob": "APPROVED"})
        self.assertEqual(closure_exemptions(snapshot=value), ("approval",))
        for state, expected in (("CHANGES_REQUESTED", ()), ("DISMISSED", ())):
            with self.subTest(state=state):
                changed = replace(value, reviews=(approval, replace(comment, state=state)))
                self.assertEqual(closure_exemptions(snapshot=changed), expected)

    def test_bot_and_keep_open_are_independent(self) -> None:

        value = snapshot(author_type="Bot", labels=("keep-open",))
        self.assertEqual(closure_exemptions(snapshot=value), ("bot", "keep-open"))

    def test_legacy_stale_does_not_authorize_closure(self) -> None:

        value = snapshot(labels=("stale",))
        entry = observe_activity(snapshot=value, previous=None)
        self.assertTrue(warning_needed(snapshot=value, entry=entry, now=fixed_clock()))
        self.assertFalse(closure_due(snapshot=value, entry=entry, now=fixed_clock()))

    def test_receipt_deadline_must_match_server_and_immutable_interval(self) -> None:

        value = snapshot()
        entry = observe_activity(snapshot=value, previous=None)
        cycle = WarningCycle(
            cycle="cycle",
            delivered_at=OLD,
            deadline="2026-07-15T12:00:00+00:00",
            initial_operation="initial",
            final_operation="final",
        )
        entry = replace(entry, activity_at="2026-05-01T12:00:00+00:00")
        initial_body = notice_body(entry=entry, operation="initial", kind="warning", cycle="cycle")
        final_body = notice_body(
            entry=entry, operation="final", kind="deadline", cycle="cycle", deadline=cycle.deadline, snapshot=value
        )
        receipts = tuple(
            Receipt(
                operation=op,
                identity=f"comment:{i}",
                actor=TRUSTED_BOT,
                kind="comment",
                at=OLD,
                content_hash=digest(body),
            )
            for i, op, body in ((1, "initial", initial_body), (1, "final", final_body))
        )
        entry = replace(entry, warning=cycle, receipts=receipts, activity_at="2026-05-01T12:00:00+00:00")
        feed = (
            FeedItem(identity="comment:1", actor=TRUSTED_BOT, kind="comment", at=OLD, content_hash=digest(final_body)),
        )
        self.assertTrue(closure_due(snapshot=replace(value, feed=feed), entry=entry, now=fixed_clock()))
        self.assertFalse(closure_due(snapshot=value, entry=entry, now=fixed_clock()))
        self.assertFalse(
            closure_due(
                snapshot=replace(value, feed=feed),
                entry=replace(entry, warning=replace(cycle, deadline=OLD)),
                now=fixed_clock(),
            )
        )
        self.assertFalse(
            closure_due(snapshot=replace(value, feed=feed, labels=("keep-open",)), entry=entry, now=fixed_clock())
        )

    def test_unfinalized_warning_cannot_close(self) -> None:

        value = snapshot()
        entry = replace(
            observe_activity(snapshot=value, previous=None),
            warning=WarningCycle(
                cycle="c", delivered_at=OLD, deadline="2026-07-15T12:00:00+00:00", initial_operation="i"
            ),
        )
        self.assertFalse(closure_due(snapshot=value, entry=entry, now=fixed_clock()))


class MutationTransport(FixtureTransport):
    def __init__(self) -> None:
        fixture = collection_transport()
        super().__init__(responses=fixture.responses, graphql=fixture.graphql)
        self.writes: list[tuple[str, str, JsonValue]] = []
        self.now = NOW
        self.next_id = 100
        self.fail_comment_after = False
        self.fail_patch_before = False
        self.approve_after_gate = False
        self.fail_after_gate = False
        self.fail_receipt_persistence = False
        root = "/repos/opsmill/infrahub"
        self.responses[root] = {"full_name": "opsmill/infrahub"}
        self.responses["/rate_limit"] = {"resources": {"core": {"remaining": 50000}, "graphql": {"remaining": 50000}}}
        self.responses[f"{root}/pulls?state=open&per_page=100&page=1"] = [{"number": 1, "id": 1}]
        self.responses[f"{root}/issues?state=all&creator=github-actions%5Bbot%5D&per_page=100&page=1"] = []
        self.responses[f"{root}/labels?per_page=100&page=1"] = []

    def write_json(self, *, method: str, path: str, payload: JsonValue, mode: Mode) -> JsonValue:  # noqa: PLR0911 - Fixture dispatch mirrors separate HTTP endpoints.
        validate_write(method=method, path=path, payload=payload, mode=mode)
        self.writes.append((method, path, payload))
        root = "/repos/opsmill/infrahub"
        data = object_value(payload)
        author: JsonValue = {"login": TRUSTED_BOT, "type": "Bot"}
        if path == f"{root}/issues":
            issue: JsonValue = {"number": 99, "id": 99, "body": data["body"], "user": author}
            self.responses[f"{root}/issues/99"] = issue
            self.responses[f"{root}/issues?state=all&creator=github-actions%5Bbot%5D&per_page=100&page=1"] = [issue]
            return issue
        if path == f"{root}/issues/99":
            ledger = decode_ledger(body=string(data["body"]))
            if self.fail_receipt_persistence and any(entry.receipts for entry in ledger.entries):
                raise IncompleteDataError("Fixture state finalization failed")
            object_value(self.responses[path])["body"] = data["body"]
            return self.responses[path]
        if path.startswith(f"{root}/labels/") and method == "DELETE":
            self.responses[f"{root}/labels?per_page=100&page=1"] = [
                item
                for item in array(self.responses[f"{root}/labels?per_page=100&page=1"])
                if object_value(item)["name"] != path.rsplit("/", 1)[1]
            ]
            return None
        if path == f"{root}/labels":
            array(self.responses[f"{root}/labels?per_page=100&page=1"]).append(data)
            return data
        pr = object_value(self.responses[f"{root}/pulls/1"])
        comments = array(self.responses[f"{root}/issues/1/comments?per_page=100&page=1"])
        if "/comments/" in path:
            if self.fail_patch_before:
                raise IncompleteDataError("Fixture edit failed")
            comment = next(
                object_value(item) for item in comments if str(object_value(item)["id"]) == path.rsplit("/", 1)[1]
            )
            comment.update(body=data["body"], updated_at=self.now)
            pr["updated_at"] = self.now
            return comment
        if path.endswith("/comments"):
            self.next_id += 1
            comment = {
                "id": self.next_id,
                "body": data["body"],
                "created_at": self.now,
                "updated_at": self.now,
                "user": author,
            }
            comments.append(comment)
            pr["updated_at"] = self.now
            if self.fail_comment_after:
                self.fail_comment_after = False
                raise IncompleteDataError("Fixture lost successful response")
            return comment
        label = string(array(data["labels"])[0]) if method == "POST" else path.rsplit("/", 1)[1]
        labels = array(pr["labels"])
        if method == "POST":
            labels.append({"name": label})
        else:
            pr["labels"] = [item for item in labels if object_value(item)["name"] != label]
        self.next_id += 1
        array(self.responses[f"{root}/issues/1/timeline?per_page=100&page=1"]).append(
            {
                "id": self.next_id,
                "event": "labeled" if method == "POST" else "unlabeled",
                "label": {"name": label},
                "created_at": self.now,
                "actor": author,
            }
        )
        pr["updated_at"] = self.now
        if self.fail_after_gate and label.startswith("lifecycle-close-") and method == "POST":
            del self.responses[f"{root}/pulls/1"]
        if self.approve_after_gate and label.startswith("lifecycle-close-") and method == "POST":
            array(self.responses[f"{root}/pulls/1/reviews?per_page=100&page=1"]).append(
                {"id": 500, "user": {"login": "bob"}, "state": "APPROVED", "submitted_at": self.now}
            )
        return []


class TestMutationLifecycle(unittest.TestCase):
    def lifecycle(self, transport: MutationTransport) -> Lifecycle:
        lifecycle = Lifecycle(
            transport=transport, clock=lambda: datetime.fromisoformat(transport.now), run_id="123", attempt="1"
        )
        lifecycle.load()
        return lifecycle

    def test_real_shaped_comment_receipts_recover_and_rerun_without_duplicate(self) -> None:
        transport = MutationTransport()
        transport.fail_comment_after = True
        lifecycle = self.lifecycle(transport)
        lifecycle.reconcile()
        entry = lifecycle.entry(1)
        self.assertIsNotNone(entry)
        if entry is None or entry.warning is None:
            self.fail("Expected active warning")
        self.assertEqual(entry.warning.deadline, "2026-10-12T12:00:00+00:00")
        self.assertEqual(entry.activity_at, OLD)
        self.lifecycle(transport).reconcile()
        comments = array(transport.responses["/repos/opsmill/infrahub/issues/1/comments?per_page=100&page=1"])
        self.assertEqual(len(comments), 1)
        self.assertTrue(
            all("state" not in object_value(payload) and "/merge" not in path for _, path, payload in transport.writes)
        )

    def test_initial_delivery_survives_deadline_edit_failure_without_arming(self) -> None:
        transport = MutationTransport()
        transport.fail_patch_before = True
        lifecycle = self.lifecycle(transport)
        with self.assertRaisesRegex(IncompleteDataError, "Fixture edit failed"):
            lifecycle.reconcile()
        stored = decode_ledger(
            body=string(object_value(transport.responses["/repos/opsmill/infrahub/issues/99"])["body"])
        )
        entry = stored.entries[0]
        self.assertIsNotNone(entry.warning)
        self.assertIsNotNone(entry.pending)
        self.assertFalse(
            closure_due(
                snapshot=collect_snapshot(transport=transport, number=1, now=fixed_clock()),
                entry=entry,
                now=datetime(2027, 1, 1, tzinfo=UTC),
            )
        )

    def test_gate_refresh_catches_approval_and_cleanup_keeps_keep_open(self) -> None:
        transport = MutationTransport()
        lifecycle = self.lifecycle(transport)
        lifecycle.reconcile()
        transport.now = "2026-10-13T12:00:00+00:00"
        transport.approve_after_gate = True
        self.assertEqual(lifecycle.prepare(), ())
        labels = object_value(transport.responses["/repos/opsmill/infrahub/pulls/1"])["labels"]
        self.assertEqual(labels, [{"name": "lifecycle-warning"}])
        self.assertTrue(any(path.endswith("/labels/lifecycle-close-123-1") for _, path, _ in transport.writes))

    def test_apply_transport_rejects_closing_merging_and_manual_label_changes(self) -> None:
        transport = MutationTransport()
        cases: tuple[tuple[str, str, JsonValue], ...] = (
            ("PATCH", "/issues/1", {"state": "closed"}),
            ("PUT", "/pulls/1/merge", {}),
            ("DELETE", "/issues/1/labels/keep-open", {}),
        )
        for method, path, payload in cases:
            with self.subTest(path=path), self.assertRaisesRegex(IncompleteDataError, "Unsupported"):
                transport.write_json(
                    method=method, path="/repos/opsmill/infrahub" + path, payload=payload, mode=Mode.APPLY
                )
        self.assertEqual(transport.writes, [])

    def test_delayed_missing_finalization_gets_fresh_full_warning(self) -> None:
        transport = MutationTransport()
        transport.fail_patch_before = True
        with self.assertRaisesRegex(IncompleteDataError, "Fixture edit failed"):
            self.lifecycle(transport).reconcile()
        transport.fail_patch_before = False
        transport.now = "2026-10-05T12:00:00+00:00"
        lifecycle = self.lifecycle(transport)
        lifecycle.reconcile()
        canceled = lifecycle.entry(1)
        if canceled is None:
            self.fail("Missing cancellation entry")
        self.assertIsNone(canceled.warning)
        transport.now = "2026-10-06T12:00:00+00:00"
        lifecycle = self.lifecycle(transport)
        lifecycle.reconcile()
        entry = lifecycle.entry(1)
        if entry is None or entry.warning is None:
            self.fail("Expected fresh warning")
        self.assertEqual(entry.warning.deadline, "2026-10-20T12:00:00+00:00")
        comments = array(transport.responses["/repos/opsmill/infrahub/issues/1/comments?per_page=100&page=1"])
        self.assertEqual(len(comments), 3)
        self.assertIn("canceled", string(object_value(comments[1])["body"]))

    def test_overlapping_comment_and_timeline_receipts_are_one_delivery(self) -> None:
        transport = MutationTransport()
        lifecycle = self.lifecycle(transport)
        lifecycle.reconcile()
        comment = object_value(
            array(transport.responses["/repos/opsmill/infrahub/issues/1/comments?per_page=100&page=1"])[0]
        )
        array(transport.responses["/repos/opsmill/infrahub/issues/1/timeline?per_page=100&page=1"]).append(
            {**comment, "event": "commented"}
        )
        value = collect_snapshot(transport=transport, number=1, now=fixed_clock())
        intent = Intent(
            operation="same", kind="comment", content_hash=digest(comment["body"]), prior_hash=value.fingerprint
        )
        receipt = recover_receipt(intent=intent, feed=value.feed)
        self.assertIsNotNone(receipt)
        if receipt is None:
            self.fail("Expected deduplicated receipt")
        self.assertEqual(receipt.identity, "comment:101")

    def test_low_mutation_quota_stops_before_any_write(self) -> None:
        transport = MutationTransport()
        transport.responses["/rate_limit"] = {"resources": {"core": {"remaining": 100}, "graphql": {"remaining": 100}}}
        with self.assertRaisesRegex(IncompleteDataError, "planned mutations"):
            self.lifecycle(transport).reconcile()
        self.assertEqual(transport.writes, [])

    def test_rejected_label_mutation_cannot_report_success(self) -> None:
        for present in (True, False):
            with self.subTest(present=present):
                transport = MutationTransport()
                pr = object_value(transport.responses["/repos/opsmill/infrahub/pulls/1"])
                pr["labels"] = [] if present else [{"name": "lifecycle-warning"}]

                def reject_label(
                    *, method: str, path: str, payload: JsonValue, mode: Mode, target: MutationTransport = transport
                ) -> JsonValue:
                    if "/issues/1/labels" in path:
                        raise IncompleteDataError("Rejected label mutation")
                    return MutationTransport.write_json(target, method=method, path=path, payload=payload, mode=mode)

                with patch.object(transport, "write_json", side_effect=reject_label):
                    with self.assertRaisesRegex(IncompleteDataError, "Rejected label mutation"):
                        self.lifecycle(transport).label(number=1, label="lifecycle-warning", present=present)
                self.assertEqual(pr["labels"], [] if present else [{"name": "lifecycle-warning"}])

    def test_human_activity_cancels_once_and_preserves_keep_open(self) -> None:
        transport = MutationTransport()
        self.lifecycle(transport).reconcile()
        transport.now = "2026-10-01T12:00:00+00:00"
        pr = object_value(transport.responses["/repos/opsmill/infrahub/pulls/1"])
        pr["updated_at"] = transport.now
        array(pr["labels"]).append({"name": "keep-open"})
        self.lifecycle(transport).reconcile()
        self.lifecycle(transport).reconcile()
        comments = array(transport.responses["/repos/opsmill/infrahub/issues/1/comments?per_page=100&page=1"])
        self.assertEqual(len(comments), 2)
        self.assertEqual(pr["labels"], [{"name": "keep-open"}])

    def test_incomplete_post_gate_refresh_disables_entire_closer(self) -> None:
        transport = MutationTransport()
        self.lifecycle(transport).reconcile()
        transport.now = "2026-10-13T12:00:00+00:00"
        transport.fail_after_gate = True
        with tempfile.TemporaryDirectory() as directory:
            report = apply_command(
                command="prepare-close",
                transport=transport,
                clock=lambda: datetime.fromisoformat(transport.now),
                run_id="123",
                attempt="1",
                state_path=Path(directory) / "state.json",
                pass_number=1,
                ref="refs/heads/stable",
            )
        self.assertFalse(report["closure_ready"])
        self.assertFalse(report["complete"])
        self.assertEqual(report["error"], "Missing fixture response")

    def test_successful_gate_and_finalization_remove_only_owned_labels(self) -> None:
        transport = MutationTransport()
        lifecycle = self.lifecycle(transport)
        lifecycle.reconcile()
        transport.now = "2026-10-13T12:00:00+00:00"
        self.assertEqual(lifecycle.prepare(), (1,))
        root = "/repos/opsmill/infrahub"
        transport.responses[f"{root}/issues?state=open&labels=lifecycle-close-123-1&per_page=100&page=1"] = []
        lifecycle.finalize()
        self.assertEqual(
            object_value(transport.responses[f"{root}/pulls/1"])["labels"], [{"name": "lifecycle-warning"}]
        )
        self.assertEqual(
            [object_value(item)["name"] for item in array(transport.responses[f"{root}/labels?per_page=100&page=1"])],
            ["lifecycle-approved", "lifecycle-bot", "lifecycle-warning"],
        )

    def test_warning_migration_preserves_legacy_label_but_starts_new_receipt(self) -> None:
        transport = MutationTransport()
        pr = object_value(transport.responses["/repos/opsmill/infrahub/pulls/1"])
        pr["labels"] = [{"name": "stale"}]
        lifecycle = self.lifecycle(transport)
        lifecycle.reconcile()
        entry = lifecycle.entry(1)
        if entry is None or entry.warning is None:
            self.fail("Expected fresh warning")
        self.assertEqual(entry.warning.delivered_at, NOW)
        self.assertEqual(pr["labels"], [{"name": "stale"}, {"name": "lifecycle-warning"}])

    def test_noop_reconciliation_collects_each_pr_only_once(self) -> None:
        transport = MutationTransport()
        self.lifecycle(transport).reconcile()
        transport.paths.clear()
        writes = len(transport.writes)
        self.lifecycle(transport).reconcile()
        self.assertEqual(transport.paths.count("/repos/opsmill/infrahub/pulls/1"), 1)
        self.assertEqual(transport.writes[writes:], [])

    def test_failed_receipt_persistence_recovers_before_activity_comparison(self) -> None:
        transport = MutationTransport()
        transport.fail_receipt_persistence = True
        with self.assertRaisesRegex(IncompleteDataError, "state finalization failed"):
            self.lifecycle(transport).reconcile()
        transport.fail_receipt_persistence = False
        transport.now = "2026-09-29T12:00:00+00:00"
        lifecycle = self.lifecycle(transport)
        lifecycle.reconcile()
        entry = lifecycle.entry(1)
        if entry is None or entry.warning is None:
            self.fail("Expected recovered warning")
        self.assertEqual(entry.activity_at, OLD)
        self.assertEqual(entry.warning.deadline, "2026-10-13T12:00:00+00:00")


class TestReminderPolicy(unittest.TestCase):
    def test_routing_and_readiness_precedence(self) -> None:
        approval = Review(identity=1, author="bob", state="APPROVED", submitted_at=OLD)
        changes = replace(approval, state="CHANGES_REQUESTED")
        clean = snapshot().aggregate
        cases = (
            (snapshot(draft=True, requested_users=("bob",)), "draft", ("alice",), "finish"),
            (snapshot(), "waiting for author", ("alice",), "request review"),
            (snapshot(reviews=(changes,), requested_users=("charlie",)), "blocked", ("alice",), "requested changes"),
            (snapshot(requested_teams=("network",)), "waiting for review", ("opsmill/network",), "review"),
            (
                snapshot(
                    reviews=(approval,),
                    requested_users=("charlie",),
                    aggregate=replace(clean, review_decision="REVIEW_REQUIRED", merge_state="BLOCKED"),
                ),
                "blocked",
                ("charlie",),
                "review",
            ),
            (
                snapshot(reviews=(approval,), aggregate=replace(clean, merge_state="BLOCKED")),
                "blocked",
                ("alice",),
                "requirements",
            ),
            (
                snapshot(reviews=(approval,), aggregate=replace(clean, mergeable="UNKNOWN")),
                "blocked",
                ("alice",),
                "requirements",
            ),
            (
                snapshot(reviews=(approval,), aggregate=replace(clean, head="old")),
                "blocked",
                ("alice",),
                "requirements",
            ),
            (snapshot(reviews=(approval,)), "ready to merge", ("alice",), "merge"),
            (snapshot(reviews=(approval,), checks=("failure",)), "blocked", ("alice",), "checks"),
            (snapshot(labels=("state/draft",)), "waiting for author", ("alice",), "request review"),
        )
        for value, category, actors, action in cases:
            with self.subTest(value=value):
                result = classify(snapshot=value, entry=observe_activity(snapshot=value, previous=None))
                self.assertEqual(result.category, category)
                self.assertEqual(result.actors, actors)
                self.assertIn(action, result.action)

    def test_calendar_windows_and_strongest_suppression(self) -> None:
        value = snapshot()
        warning = WarningCycle(
            cycle="c",
            delivered_at=NOW,
            deadline="2026-10-12T12:00:00+00:00",
            initial_operation="i",
            final_operation="f",
        )
        entry = replace(observe_activity(snapshot=value, previous=None), warning=warning)
        for at, expected in (
            ("2026-10-04T23:59:00+00:00", None),
            ("2026-10-05T00:00:00+00:00", "milestone-7"),
            ("2026-10-11T00:00:00+00:00", "milestone-1"),
            ("2026-10-12T11:59:00+00:00", "milestone-1"),
            ("2026-10-12T12:00:00+00:00", None),
        ):
            with self.subTest(at=at):
                self.assertEqual(next_notice(snapshot=value, entry=entry, now=datetime.fromisoformat(at)), expected)
        entry = replace(entry, warning=replace(warning, milestones=("milestone-1",)))
        self.assertIsNone(
            next_notice(snapshot=value, entry=entry, now=datetime.fromisoformat("2026-10-11T09:00:00+00:00"))
        )

    def test_ordinary_seven_day_cadence_and_exempt_messages(self) -> None:
        for value in (
            snapshot(draft=True),
            snapshot(labels=("keep-open",)),
            snapshot(reviews=(Review(identity=1, author="bob", state="APPROVED", submitted_at=OLD),)),
        ):
            entry = replace(observe_activity(snapshot=value, previous=None), activity_at="2026-09-21T12:00:00+00:00")
            self.assertIsNone(
                next_notice(snapshot=value, entry=entry, now=datetime.fromisoformat("2026-09-28T11:59:59+00:00"))
            )
            self.assertEqual(next_notice(snapshot=value, entry=entry, now=fixed_clock()), "ordinary")
            self.assertIsNone(
                next_notice(
                    snapshot=value, entry=replace(entry, last_notice_at="2026-09-22T12:00:00+00:00"), now=fixed_clock()
                )
            )
            body = notice_body(entry=entry, snapshot=value, operation="ordinary:test", kind="ordinary")
            self.assertIn("@alice", body)
            self.assertNotIn("closure", body.lower())

    def test_latest_status_per_context_replaces_historical_failure(self) -> None:
        transport = collection_transport()
        transport.responses["/repos/opsmill/infrahub/commits/abc/statuses?per_page=100&page=1"] = [
            {"id": 2, "context": "ci", "state": "success", "created_at": NOW},
            {"id": 1, "context": "ci", "state": "failure", "created_at": OLD},
        ]
        self.assertEqual(collect_snapshot(transport=transport, number=1, now=fixed_clock()).checks, ("success",))


class TestReminderLifecycle(unittest.TestCase):
    lifecycle = TestMutationLifecycle.lifecycle

    def test_weekly_warning_milestones_and_gate(self) -> None:
        transport = MutationTransport()
        transport.now = "2026-07-08T12:00:00+00:00"
        transport.fail_comment_after = True
        lifecycle = self.lifecycle(transport)
        lifecycle.reconcile()
        comments = array(transport.responses["/repos/opsmill/infrahub/issues/1/comments?per_page=100&page=1"])
        self.assertEqual(len(comments), 1)
        self.assertIn("@alice", string(object_value(comments[0])["body"]))
        self.lifecycle(transport).reconcile()
        self.assertEqual(len(comments), 1)
        transport.now = NOW
        lifecycle = self.lifecycle(transport)
        lifecycle.reconcile()
        self.assertEqual(len(comments), 2)
        for at in ("2026-10-05T09:00:00+00:00", "2026-10-11T08:00:00+00:00"):
            transport.now = at
            self.lifecycle(transport).reconcile()
            self.lifecycle(transport).reconcile()
        self.assertEqual(len(comments), 4)
        self.assertIn("2026-10-12T12:00:00+00:00", string(object_value(comments[-1])["body"]))
        self.assertEqual(self.lifecycle(transport).prepare(), ())
        transport.now = "2026-10-12T12:00:00+00:00"
        self.assertEqual(self.lifecycle(transport).prepare(), (1,))
        self.assertEqual(len(comments), 4)
        self.assertTrue(all("state" not in object_value(payload) for _, _, payload in transport.writes))

    def test_missed_middle_window_posts_only_final(self) -> None:
        transport = MutationTransport()
        self.lifecycle(transport).reconcile()
        transport.now = "2026-10-11T08:00:00+00:00"
        self.lifecycle(transport).reconcile()
        comments = array(transport.responses["/repos/opsmill/infrahub/issues/1/comments?per_page=100&page=1"])
        self.assertEqual(len(comments), 2)
        self.assertIn('"kind":"milestone-1"', string(object_value(comments[-1])["body"]))
        transport.now = "2026-10-13T08:00:00+00:00"
        self.lifecycle(transport).reconcile()
        self.assertEqual(len(comments), 2)

    def test_ordinary_receipt_recovers_and_rate_limits_by_delivery(self) -> None:
        transport = MutationTransport()
        transport.now = "2026-07-08T13:00:00+00:00"
        transport.fail_receipt_persistence = True
        with self.assertRaisesRegex(IncompleteDataError, "state finalization failed"):
            self.lifecycle(transport).reconcile()
        transport.fail_receipt_persistence = False
        transport.now = "2026-07-15T12:00:00+00:00"
        self.lifecycle(transport).reconcile()
        comments = array(transport.responses["/repos/opsmill/infrahub/issues/1/comments?per_page=100&page=1"])
        self.assertEqual(len(comments), 1)
        transport.now = "2026-07-15T13:00:00+00:00"
        lifecycle = self.lifecycle(transport)
        lifecycle.reconcile()
        self.assertEqual(len(comments), 2)
        entry = lifecycle.entry(1)
        if entry is None:
            self.fail("Missing entry")
        self.assertEqual(entry.activity_at, OLD)
        self.assertEqual(entry.last_notice_at, transport.now)

    def test_fresh_reviewers_reroute_ordinary_and_warning_names_all(self) -> None:
        transport = MutationTransport()
        transport.now = "2026-07-08T12:00:00+00:00"
        lifecycle = self.lifecycle(transport)
        lifecycle.collect_reconciliation()
        transport.responses["/repos/opsmill/infrahub/pulls/1/requested_reviewers?per_page=100&page=1"] = {
            "users": [{"login": "charlie"}],
            "teams": [{"slug": "network"}],
        }
        lifecycle.reconcile_one(1)
        comments = array(transport.responses["/repos/opsmill/infrahub/issues/1/comments?per_page=100&page=1"])
        ordinary = string(object_value(comments[0])["body"])
        self.assertIn("@charlie, @opsmill/network: please review", ordinary)
        self.assertNotIn("@alice", ordinary)
        transport.now = NOW
        self.lifecycle(transport).reconcile()
        warning = string(object_value(comments[-1])["body"])
        self.assertIn("@alice, @charlie, @opsmill/network", warning)
        self.assertIn("2026-10-12T12:00:00+00:00", warning)

    def test_human_reset_after_milestone_neutralizes_only_once(self) -> None:
        transport = MutationTransport()
        self.lifecycle(transport).reconcile()
        transport.now = "2026-10-05T08:00:00+00:00"
        self.lifecycle(transport).reconcile()
        transport.now = "2026-10-06T08:00:00+00:00"
        comments = array(transport.responses["/repos/opsmill/infrahub/issues/1/comments?per_page=100&page=1"])
        comments.append(
            {
                "id": 900,
                "body": "Working on this",
                "user": {"login": "alice"},
                "created_at": transport.now,
                "updated_at": transport.now,
            }
        )
        lifecycle = self.lifecycle(transport)
        lifecycle.reconcile()
        self.lifecycle(transport).reconcile()
        self.assertEqual(len(comments), 4)
        self.assertIn("canceled", string(object_value(comments[-1])["body"]))
        self.assertEqual(self.lifecycle(transport).prepare(), ())

    def test_observation_uses_saved_ordinary_receipt_without_writes(self) -> None:
        transport = MutationTransport()
        transport.now = "2026-07-08T12:00:00+00:00"
        self.lifecycle(transport).reconcile()
        transport.responses["/repos/opsmill/infrahub/pulls?state=open&per_page=100&page=1"] = [
            {"id": 1, "number": 1, "user": {"login": "alice", "type": "User"}}
        ]
        writes = len(transport.writes)
        report = observe(
            repository="opsmill/infrahub",
            transport=transport,
            clock=lambda: datetime.fromisoformat("2026-07-09T12:00:00+00:00"),
        )
        self.assertTrue(report.complete)
        self.assertEqual(report.proposals[0].activity_at, OLD)
        self.assertIsNone(report.proposals[0].notice)
        self.assertEqual(len(transport.writes), writes)


if __name__ == "__main__":
    unittest.main()


class TestDashboard(unittest.TestCase):
    lifecycle = TestMutationLifecycle.lifecycle

    def test_preview_escapes_content_and_has_honest_clocks(self) -> None:
        transport = observation_transport()
        pr = object_value(transport.responses["/repos/opsmill/infrahub/pulls/1"])
        pr["title"] = "hello | <script> @alice\n[bad](https://example.com)"
        report = observe(repository="opsmill/infrahub", transport=transport, clock=fixed_clock)
        body = render_dashboard(report=report, ledger=Ledger(), preview=True)
        self.assertIn("Observation preview", body)
        self.assertIn("Last successful refresh: never", body)
        self.assertIn("Days inactive", body)
        self.assertIn("hello &#124; &lt;script&gt; &#64;alice", body)
        self.assertNotIn("@alice", body)
        self.assertNotIn("[bad]", body)
        for heading in (
            "Ready to merge",
            "Waiting for review",
            "Waiting for author / Needs reviewer",
            "Blocked",
            "Drafts",
            "Closing soon",
            "Bot-authored PRs",
        ):
            self.assertIn(heading, body)

    def test_bot_rows_require_no_supplemental_reads(self) -> None:
        transport = observation_transport(bots=True)
        report = observe(repository="opsmill/infrahub", transport=transport, clock=fixed_clock)
        body = render_dashboard(report=report, ledger=Ledger(), preview=True)
        self.assertIn("dependabot", body)
        self.assertIn("Excluded from reminders and cleanup", body)
        self.assertFalse(any("/pulls/1" in path for path in transport.paths))

    def test_visible_body_survives_intermediate_persistence(self) -> None:
        transport = MutationTransport()
        lifecycle = self.lifecycle(transport)
        lifecycle.persist(visible="Previously successful dashboard")
        lifecycle.persist(entry=observe_activity(snapshot=snapshot(), previous=None))
        if lifecycle.dashboard is None:
            self.fail("Expected persisted dashboard")
        self.assertTrue(lifecycle.dashboard[1].startswith("Previously successful dashboard\n"))
        self.assertEqual(sum(method == "POST" and path.endswith("/issues") for method, path, _ in transport.writes), 1)
        self.assertFalse(any("/comments" in path for _, path, _ in transport.writes))

    def test_oversize_and_partial_preview_fail_closed(self) -> None:
        report = observe(repository="opsmill/infrahub", transport=observation_transport(), clock=fixed_clock)
        huge = replace(report.inventory[0], title="x" * 60000)
        with self.assertRaisesRegex(IncompleteDataError, "60000"):
            render_dashboard(report=replace(report, inventory=(huge,)), ledger=Ledger(), preview=True)
        with self.assertRaisesRegex(IncompleteDataError, "incomplete"):
            render_dashboard(report=replace(report, complete=False), ledger=Ledger(), preview=True)

    def test_explicit_adoption_and_duplicate_rejection(self) -> None:
        path = "/repos/opsmill/infrahub/issues?state=all&creator=github-actions%5Bbot%5D&per_page=100&page=1"
        issue: dict[str, JsonValue] = {
            "number": 99,
            "id": 99,
            "title": "PR lifecycle dashboard",
            "body": "Existing human dashboard",
            "user": {"login": "maintainer", "type": "User"},
        }
        transport = FixtureTransport(responses={path: [], "/repos/opsmill/infrahub/issues/99": issue})
        self.assertIsNone(discover_dashboard(transport=transport))
        self.assertEqual(discover_dashboard(transport=transport, adopted_issue=99), (99, "Existing human dashboard"))
        transport.responses[path] = [
            {"id": 100, "number": 100, "body": DASHBOARD_MARKER, "user": {"login": TRUSTED_BOT, "type": "Bot"}}
        ]
        with self.assertRaisesRegex(IncompleteDataError, "Multiple dashboards"):
            discover_dashboard(transport=transport, adopted_issue=99)

    def test_final_refresh_reuses_issue_and_preserves_success_on_failure(self) -> None:
        transport = MutationTransport()
        root = "/repos/opsmill/infrahub"
        transport.responses[f"{root}/pulls?state=open&per_page=100&page=1"] = [
            {"id": 1, "number": 1, "user": {"login": "alice", "type": "User"}}
        ]
        lifecycle = self.lifecycle(transport)
        lifecycle.reconcile()
        lifecycle.finalize()
        lifecycle.refresh_dashboard()
        self.assertEqual(lifecycle.ledger.last_successful_refresh, NOW)
        if lifecycle.dashboard is None:
            self.fail("Expected persisted dashboard")
        successful = lifecycle.dashboard[1]
        self.assertIn("## Closing soon (1)", successful)
        self.assertIn("closure deadline: 2026-10-12T12:00:00+00:00", successful)
        writes = len(transport.writes)
        lifecycle.refresh_dashboard()
        self.assertEqual(len(transport.writes), writes)
        transport.now = "2026-09-29T12:00:00+00:00"
        del transport.responses[f"{root}/pulls/1/reviews?per_page=100&page=1"]
        with self.assertRaisesRegex(IncompleteDataError, "Dashboard refresh failed"):
            lifecycle.refresh_dashboard()
        self.assertEqual(lifecycle.dashboard[1], successful)
        self.assertEqual(lifecycle.ledger.last_successful_refresh, NOW)

    def test_render_places_each_category_once_with_plain_actors(self) -> None:
        report = observe(repository="opsmill/infrahub", transport=observation_transport(count=6), clock=fixed_clock)
        categories = ("ready to merge", "waiting for review", "waiting for author", "blocked", "draft", "closing soon")
        proposals = tuple(
            replace(
                item, classification=replace(item.classification, category=category, actors=("alice", "opsmill/team"))
            )
            for item, category in zip(report.proposals, categories, strict=True)
        )
        body = render_dashboard(report=replace(report, proposals=proposals), ledger=Ledger())
        for number in range(1, 7):
            self.assertEqual(body.count(f"[#{number}]"), 1)
        self.assertEqual(body.count("alice, opsmill/team:"), 6)
        self.assertNotIn("@", body)

    def test_compact_history_detects_old_edits_and_owned_deletion(self) -> None:
        history = tuple(
            FeedItem(identity=f"comment:{number}", actor="alice", kind="comment", at=OLD, content_hash=str(number))
            for number in range(2000)
        )
        value = snapshot(feed=history)
        entry = observe_activity(snapshot=value, previous=None)
        self.assertEqual(entry.watermarks, ())
        self.assertLess(len(encode_ledger(ledger=Ledger(entries=(entry,)))), 1500)
        edited = (replace(history[0], content_hash="edited"), *history[1:])
        self.assertEqual(observe_activity(snapshot=replace(value, feed=edited), previous=entry).activity_at, NOW)
        owned = Receipt(
            operation="ordinary:1",
            identity="comment:owned",
            actor=TRUSTED_BOT,
            kind="comment",
            at=OLD,
            content_hash="notice",
        )
        item = FeedItem(
            identity=owned.identity, actor=owned.actor, kind=owned.kind, at=owned.at, content_hash=owned.content_hash
        )
        initial = observe_activity(snapshot=snapshot(), previous=None)
        tracked = observe_activity(snapshot=snapshot(feed=(item,)), previous=replace(initial, receipts=(owned,)))
        self.assertEqual(tracked.activity_at, OLD)
        deleted = observe_activity(snapshot=snapshot(), previous=tracked)
        self.assertEqual(deleted.activity_at, NOW)

    def test_pruning_rebases_receipts_without_resetting_activity(self) -> None:
        transport = MutationTransport()
        lifecycle = self.lifecycle(transport)
        lifecycle.reconcile()
        for day in ("2026-10-05T12:00:00+00:00", "2026-10-11T12:00:00+00:00"):
            transport.now = day
            lifecycle = self.lifecycle(transport)
            lifecycle.reconcile()
        before = lifecycle.ledger.entries[0]
        value = collect_snapshot(transport=transport, number=1, now=datetime.fromisoformat(transport.now))
        retained = prune_ledger(
            ledger=lifecycle.ledger, confirmed_closed=frozenset(), gates_cleaned=frozenset(), snapshots=(value,)
        ).entries[0]
        self.assertEqual(retained.warning, before.warning)
        self.assertTrue(closure_due(snapshot=value, entry=retained, now=datetime(2026, 10, 13, tzinfo=UTC)))
        retired = prune_ledger(
            ledger=Ledger(entries=(replace(retained, warning=None),)),
            confirmed_closed=frozenset(),
            gates_cleaned=frozenset(),
            snapshots=(value,),
        ).entries[0]
        self.assertEqual(retired.receipts, ())
        self.assertEqual(observe_activity(snapshot=value, previous=retired).activity_at, retained.activity_at)
        pending = replace(
            retained,
            pending=Intent(operation="pending", kind="comment", content_hash="x", prior_hash=retained.fingerprint),
        )
        self.assertEqual(
            prune_ledger(
                ledger=Ledger(entries=(pending,)),
                confirmed_closed=frozenset({1}),
                gates_cleaned=frozenset({1}),
                snapshots=(value,),
            ).entries,
            (pending,),
        )

    def test_label_recovery_rejects_two_identical_added_events(self) -> None:
        entry = observe_activity(snapshot=snapshot(), previous=None)
        intent = Intent(
            operation="label",
            kind="labeled",
            content_hash="label-hash",
            prior_hash=entry.fingerprint,
            feed_baseline=feed_digest(()),
        )
        events = tuple(
            FeedItem(
                identity=f"timeline:{number}", actor=TRUSTED_BOT, kind="labeled", at=NOW, content_hash="label-hash"
            )
            for number in (1, 2)
        )
        with self.assertRaisesRegex(IncompleteDataError, "baseline"):
            reconcile_pending(snapshot=snapshot(feed=events), previous=replace(entry, pending=intent))
        recovered = reconcile_pending(snapshot=snapshot(feed=events[:1]), previous=replace(entry, pending=intent))
        if recovered is None:
            self.fail("Expected recovered receipt")
        self.assertEqual(recovered.receipts[0].identity, "timeline:1")

    def test_forged_current_digest_cannot_hide_post_warning_human_activity(self) -> None:
        transport = MutationTransport()
        lifecycle = self.lifecycle(transport)
        lifecycle.reconcile()
        value = collect_snapshot(transport=transport, number=1, now=fixed_clock())
        entry = lifecycle.ledger.entries[0]
        human = FeedItem(
            identity="comment:human",
            actor="alice",
            kind="comment",
            at="2026-09-29T12:00:00+00:00",
            content_hash="human activity",
        )
        changed = replace(value, feed=(*value.feed, human))
        forged = replace(entry, external_digest=activity_digest(snapshot=changed, receipts=entry.receipts))
        self.assertFalse(closure_due(snapshot=changed, entry=forged, now=datetime(2026, 10, 13, tzinfo=UTC)))

    def test_repeated_confirmed_deliveries_keep_bounded_state_and_old_edit_detection(self) -> None:
        entry = observe_activity(snapshot=snapshot(), previous=None)
        feed: tuple[FeedItem, ...] = ()
        for index in range(100):
            receipt = Receipt(
                operation=f"ordinary:{index}",
                identity=f"comment:{index}",
                actor=TRUSTED_BOT,
                kind="comment",
                at=NOW,
                content_hash=digest(str(index)),
            )
            feed = (
                *feed,
                FeedItem(
                    identity=receipt.identity,
                    actor=receipt.actor,
                    kind=receipt.kind,
                    at=receipt.at,
                    content_hash=receipt.content_hash,
                ),
            )
            value = snapshot(feed=feed, updated_at=NOW)
            entry = observe_activity(snapshot=value, previous=replace(entry, receipts=(receipt,), last_notice_at=NOW))
            entry = prune_ledger(
                ledger=Ledger(entries=(entry,)),
                confirmed_closed=frozenset(),
                gates_cleaned=frozenset(),
                snapshots=(value,),
            ).entries[0]
            self.assertEqual((entry.activity_at, entry.receipts, entry.watermarks), (OLD, (), ()))
            self.assertLess(len(encode_ledger(ledger=Ledger(entries=(entry,)))), 1500)
        edited = snapshot(
            feed=(replace(next(iter(feed)), content_hash="edited old comment"), *feed[1:]), updated_at=NOW
        )
        self.assertEqual(observe_activity(snapshot=edited, previous=entry).activity_at, NOW)

    def test_finalization_keeps_label_definition_with_open_references(self) -> None:
        transport = MutationTransport()
        transport.responses["/repos/opsmill/infrahub/labels?per_page=100&page=1"] = [
            {"id": 1, "name": "lifecycle-close-123-1"}
        ]
        transport.responses[
            "/repos/opsmill/infrahub/issues?state=open&labels=lifecycle-close-123-1&per_page=100&page=1"
        ] = [{"id": 2, "number": 2}]
        self.lifecycle(transport).finalize()
        self.assertFalse(any(method == "DELETE" for method, _, _ in transport.writes))

    def test_missing_warning_proof_prevents_successful_refresh(self) -> None:
        transport = MutationTransport()
        transport.responses["/repos/opsmill/infrahub/pulls?state=open&per_page=100&page=1"] = [
            {"id": 1, "number": 1, "user": {"login": "alice", "type": "User"}}
        ]
        lifecycle = self.lifecycle(transport)
        lifecycle.reconcile()
        entry = lifecycle.ledger.entries[0]
        lifecycle.persist(entry=replace(entry, receipts=()))
        with self.assertRaisesRegex(IncompleteDataError, "reconciliation still required"):
            lifecycle.refresh_dashboard()
        self.assertIsNone(lifecycle.ledger.last_successful_refresh)

    def test_full_inventory_with_active_cycles_fits_after_receipt_compaction(self) -> None:
        report = observe(repository="opsmill/infrahub", transport=observation_transport(count=112), clock=fixed_clock)
        entries = []
        active_count = 12
        for index, value in enumerate(report.inventory):
            entry = observe_activity(snapshot=value, previous=None)
            cycle = digest(str(index))[:24]
            warning = (
                WarningCycle(
                    cycle=cycle,
                    delivered_at=NOW,
                    deadline="2026-10-12T12:00:00+00:00",
                    initial_operation=f"warning:{cycle}",
                    final_operation=f"deadline:{cycle}",
                )
                if index < active_count
                else None
            )
            kinds = (
                ("warning", "deadline", "milestone-7", "milestone-1", "label-warning", "label-gate")
                if warning
                else ("ordinary",)
            )
            receipts = tuple(
                Receipt(
                    operation=f"{kind}:{cycle}",
                    identity=f"{kind}:{index}",
                    actor=TRUSTED_BOT,
                    kind="comment",
                    at=NOW,
                    content_hash=digest(f"{kind}:{index}"),
                )
                for kind in kinds
            )
            entries.append(replace(entry, receipts=receipts, warning=warning, last_notice_at=NOW))
        ledger = prune_ledger(
            ledger=Ledger(entries=tuple(entries)),
            confirmed_closed=frozenset(),
            gates_cleaned=frozenset(),
            snapshots=report.inventory,
        )
        body = render_dashboard(report=report, ledger=ledger)
        self.assertLess(len(body), 60000)
        self.assertEqual(body.count("](/opsmill/infrahub/pull/"), 112)
        self.assertEqual(sum(len(entry.receipts) for entry in ledger.entries), 72)
        self.assertEqual(sum(entry.last_notice_at == NOW for entry in ledger.entries), 112)
