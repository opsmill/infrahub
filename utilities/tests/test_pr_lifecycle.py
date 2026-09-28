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

from utilities.pr_lifecycle import (
    DASHBOARD_MARKER,
    TRUSTED_BOT,
    Aggregate,
    FeedItem,
    IncompleteDataError,
    Intent,
    JsonValue,
    Ledger,
    Receipt,
    Snapshot,
    collect_snapshot,
    decode_ledger,
    discover_dashboard,
    encode_ledger,
    finalize_receipt,
    main,
    observe,
    observe_activity,
    pages,
    prune_ledger,
    recover_receipt,
    stage_intent,
    verify_generation,
)


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
        self.assertEqual(len(transport.paths), 9)
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


if __name__ == "__main__":
    unittest.main()
