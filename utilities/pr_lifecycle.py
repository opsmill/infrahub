from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Callable

ALLOWED_REPOSITORY = "opsmill/infrahub"
DASHBOARD_MARKER = "<!-- infrahub-pr-lifecycle:dashboard:v1 -->"
STATE_PREFIX = "<!-- infrahub-pr-lifecycle:state:v1 "
TRUSTED_BOT = "github-actions[bot]"
PAGE_SIZE = 100
RETRIES = 3
MAX_RETRY_DELAY = 60
MAX_BODY = 60000
MAX_STATE = 4_000_000
WATERMARK_FIELDS = 2
MAX_PASSES = 4
QUOTA_RESERVE = 50
REST_READS_PER_PR = 8
DEFAULT_BUDGET = 5000
type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None


class IncompleteDataError(ValueError):
    pass


class Mode(StrEnum):
    OBSERVE = "observe"
    APPLY = "apply"


class ReadTransport(Protocol):
    def get_json(self, *, path: str) -> JsonValue: ...
    def query(self, *, number: int) -> JsonValue: ...


def object_value(value: JsonValue) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise IncompleteDataError("Expected JSON object")
    return value


def array(value: JsonValue) -> list[JsonValue]:
    if not isinstance(value, list):
        raise IncompleteDataError("Expected JSON array")
    return value


def string(value: JsonValue) -> str:
    if not isinstance(value, str):
        raise IncompleteDataError("Expected JSON string")
    return value


def integer(value: JsonValue) -> int:
    if type(value) is not int:
        raise IncompleteDataError("Expected JSON integer")
    return value


def timestamp(value: JsonValue) -> datetime:
    try:
        result = datetime.fromisoformat(string(value))
    except ValueError as exc:
        raise IncompleteDataError("Invalid timestamp") from exc
    if result.tzinfo is None:
        raise IncompleteDataError("Timestamp must have timezone")
    return result.astimezone(UTC)


def digest(value: JsonValue) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


class GitHubClient:
    def __init__(
        self, *, token: str, sleep: Callable[[float], None] = time.sleep, budget: int = DEFAULT_BUDGET
    ) -> None:
        if not token:
            raise IncompleteDataError("GH_TOKEN or GITHUB_TOKEN is required")
        self.token = token
        self.sleep = sleep
        self.requests = 0
        self.remaining: int | None = None
        self.used: int | None = None
        self.quotas: dict[str, int] = {}
        self.budget = budget

    def get_json(self, *, path: str) -> JsonValue:
        prefix = f"/repos/{ALLOWED_REPOSITORY}"
        if path not in ("/rate_limit", prefix) and not path.startswith((prefix + "/", prefix + "?")):
            raise IncompleteDataError("Read path outside allowed repository")
        return self._read(path=path)

    def query(self, *, number: int) -> JsonValue:
        query = (
            'query($number:Int!){repository(owner:"opsmill",name:"infrahub"){'
            "pullRequest(number:$number){headRefOid mergeable mergeStateStatus reviewDecision}}}"
        )
        return self._read(path="/graphql", payload={"query": query, "variables": {"number": number}})

    def _read(self, *, path: str, payload: JsonValue = None) -> JsonValue:
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(
            "https://api.github.com" + path,
            data=data,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "infrahub-pr-lifecycle",
            },
            method="GET" if data is None else "POST",
        )
        for attempt in range(RETRIES):
            if self.requests >= self.budget:
                raise IncompleteDataError("HTTP request budget exhausted")
            resource = "graphql" if path == "/graphql" else "core"
            if self.quotas.get(resource, QUOTA_RESERVE + 1) <= QUOTA_RESERVE:
                raise IncompleteDataError(f"Insufficient {resource} quota reserve")
            self.requests += 1
            try:
                with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - URL has a fixed HTTPS origin.
                    self.account_headers(headers=dict(response.headers.items()))
                    return json.loads(response.read())
            except urllib.error.HTTPError as exc:
                headers = dict(exc.headers.items())
                self.account_headers(headers=headers)
                if exc.code not in (429, 500, 502, 503, 504) and not (
                    exc.code == HTTPStatus.FORBIDDEN and self.remaining == 0
                ):
                    raise IncompleteDataError(f"GitHub read failed HTTP {exc.code}") from None
                delay = max(
                    float(headers.get("Retry-After", 2**attempt)),
                    float(headers.get("X-RateLimit-Reset", 0)) - time.time() if self.remaining == 0 else 0,
                )
                if delay > MAX_RETRY_DELAY or attempt == RETRIES - 1:
                    raise IncompleteDataError("GitHub retry budget exhausted") from None
                self.sleep(delay)
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt == RETRIES - 1:
                    raise IncompleteDataError("GitHub read unavailable after three attempts") from exc
                self.sleep(2**attempt)
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise IncompleteDataError("GitHub returned invalid JSON") from exc
        raise IncompleteDataError("GitHub retry budget exhausted")

    def write_json(self, *, method: str, path: str, payload: JsonValue, mode: Mode) -> JsonValue:
        validate_write(method=method, path=path, payload=payload, mode=mode)
        if self.requests >= self.budget or self.quotas.get("core", QUOTA_RESERVE + 1) <= QUOTA_RESERVE:
            raise IncompleteDataError("Insufficient quota for mutation and cleanup")
        request = urllib.request.Request(
            "https://api.github.com" + path,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "infrahub-pr-lifecycle",
            },
            method=method,
        )
        self.requests += 1
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - Fixed HTTPS origin.
                self.account_headers(headers=dict(response.headers.items()))
                raw = response.read()
                return json.loads(raw) if raw else None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise IncompleteDataError("Ambiguous GitHub mutation; reconcile before retry") from exc

    def account_headers(self, *, headers: dict[str, str]) -> None:
        normalized = {key.lower(): value for key, value in headers.items()}
        if "x-ratelimit-remaining" in normalized:
            self.remaining = int(normalized["x-ratelimit-remaining"])
            self.quotas[normalized.get("x-ratelimit-resource", "core")] = self.remaining
        if "x-ratelimit-used" in normalized:
            self.used = int(normalized["x-ratelimit-used"])


def pages(*, transport: ReadTransport, path: str, key: str | None = None) -> tuple[dict[str, JsonValue], ...]:
    results: list[dict[str, JsonValue]] = []
    seen: set[str] = set()
    for page in range(1, 1001):
        value = transport.get_json(path=f"{path}{'&' if '?' in path else '?'}per_page=100&page={page}")
        items = array(object_value(value).get(key)) if key else array(value)
        for item in items:
            record = object_value(item)
            identity = str(record.get("id", record.get("node_id", digest(record))))
            if identity in seen:
                raise IncompleteDataError("Duplicate item while paginating; inventory changed")
            seen.add(identity)
            results.append(record)
        if len(items) < PAGE_SIZE:
            if (
                key
                and "total_count" in object_value(value)
                and integer(object_value(value)["total_count"]) != len(results)
            ):
                raise IncompleteDataError("Paginated count mismatch")
            return tuple(results)
    raise IncompleteDataError("Pagination limit exceeded")


def requested_reviewers(
    *,
    transport: ReadTransport,
    number: int,
) -> tuple[tuple[dict[str, JsonValue], ...], tuple[dict[str, JsonValue], ...]]:
    users: list[dict[str, JsonValue]] = []
    teams: list[dict[str, JsonValue]] = []
    for page in range(1, 1001):
        value = object_value(
            transport.get_json(
                path=f"/repos/{ALLOWED_REPOSITORY}/pulls/{number}/requested_reviewers?per_page=100&page={page}"
            )
        )
        user_page, team_page = array(value.get("users")), array(value.get("teams"))
        users.extend(object_value(item) for item in user_page)
        teams.extend(object_value(item) for item in team_page)
        if len(user_page) < PAGE_SIZE and len(team_page) < PAGE_SIZE:
            for items, key in ((users, "login"), (teams, "slug")):
                if len({string(item.get(key)) for item in items}) != len(items):
                    raise IncompleteDataError("Duplicate requested reviewer during pagination")
            return tuple(users), tuple(teams)
    raise IncompleteDataError("Requested reviewer pagination limit exceeded")


@dataclass(frozen=True)
class FeedItem:
    identity: str
    actor: str
    kind: str
    at: str
    content_hash: str
    created_at: str | None = None


@dataclass(frozen=True)
class Review:
    identity: int
    author: str
    state: str
    submitted_at: str


@dataclass(frozen=True)
class Aggregate:
    head: str
    mergeable: str
    merge_state: str
    review_decision: str | None


@dataclass(frozen=True)
class Snapshot:
    number: int
    node_id: str
    title: str
    url: str
    author: str
    author_type: str
    state: str
    draft: bool
    updated_at: str
    head: str
    base: str
    labels: tuple[str, ...]
    assignees: tuple[str, ...]
    requested_users: tuple[str, ...]
    requested_teams: tuple[str, ...]
    reviews: tuple[Review, ...]
    checks: tuple[str, ...]
    aggregate: Aggregate
    feed: tuple[FeedItem, ...]
    fingerprint: str
    observed_at: str


def collect_snapshot(*, transport: ReadTransport, number: int, now: datetime) -> Snapshot:  # noqa: PLR0914 - One boundary validates a complete PR.
    root = f"/repos/{ALLOWED_REPOSITORY}"
    pr = object_value(transport.get_json(path=f"{root}/pulls/{number}"))
    draft = pr.get("draft")
    if integer(pr.get("number")) != number or not isinstance(draft, bool):
        raise IncompleteDataError("Invalid PR identity or draft state")
    author = object_value(pr.get("user"))
    head = string(object_value(pr.get("head")).get("sha"))
    feeds: list[FeedItem] = []
    reviews: list[Review] = []
    for kind, path in (
        ("comment", f"issues/{number}/comments"),
        ("review-comment", f"pulls/{number}/comments"),
        ("timeline", f"issues/{number}/timeline"),
        ("review", f"pulls/{number}/reviews"),
    ):
        for item in pages(transport=transport, path=f"{root}/{path}"):
            actor_data: JsonValue = item.get("user") or item.get("actor")
            if actor_data is None:
                actor_data = {"login": "unknown"}
            actor = object_value(actor_data)
            at = item.get("updated_at") or item.get("submitted_at") or item.get("created_at")
            if at is None:
                if kind != "timeline":
                    raise IncompleteDataError("Feed event missing timestamp")
                # Some timeline summaries have no date; their content still participates in change detection.
                at = pr.get("created_at")
            event = string(item.get("event", kind))
            feed_kind = kind
            if event == "commented":
                feed_kind, event = "comment", "comment"
            identity = item.get("id") or item.get("node_id") or digest(item)
            content: JsonValue = item
            if event == "comment" or kind == "review-comment":
                content = item.get("body")
            elif event in ("labeled", "unlabeled"):
                content = {"event": event, "label": object_value(item.get("label")).get("name")}
            feeds.append(
                FeedItem(
                    identity=f"{feed_kind}:{identity}",
                    actor=string(actor.get("login")),
                    kind=event,
                    at=timestamp(at).isoformat(),
                    content_hash=digest(content),
                    created_at=timestamp(item.get("created_at") or at).isoformat(),
                )
            )
            if kind == "review":
                reviews.append(
                    Review(
                        identity=integer(item.get("id")),
                        author=string(actor.get("login")),
                        state=string(item.get("state")),
                        submitted_at=timestamp(at).isoformat(),
                    )
                )
    users, teams = requested_reviewers(transport=transport, number=number)
    check_runs = pages(transport=transport, path=f"{root}/commits/{head}/check-runs", key="check_runs")
    statuses = pages(transport=transport, path=f"{root}/commits/{head}/statuses")
    latest_statuses: dict[str, dict[str, JsonValue]] = {}
    for status in sorted(
        statuses, key=lambda item: (timestamp(item.get("created_at")), integer(item.get("id"))), reverse=True
    ):
        latest_statuses.setdefault(string(status.get("context")), status)
    response = object_value(transport.query(number=number))
    if response.get("errors"):
        raise IncompleteDataError("GraphQL returned errors")
    aggregate = object_value(object_value(object_value(response.get("data")).get("repository")).get("pullRequest"))
    if "reviewDecision" not in aggregate:
        raise IncompleteDataError("Missing reviewDecision aggregate")
    decision = aggregate["reviewDecision"]
    if decision is not None:
        decision = string(decision)
    readiness = Aggregate(
        head=string(aggregate.get("headRefOid")),
        mergeable=string(aggregate.get("mergeable")),
        merge_state=string(aggregate.get("mergeStateStatus")),
        review_decision=decision,
    )
    if readiness.head != head:
        raise IncompleteDataError("Head changed during collection")
    labels = tuple(sorted(string(object_value(label).get("name")) for label in array(pr.get("labels"))))
    fingerprint = digest(
        {
            key: pr.get(key)
            for key in (
                "title",
                "body",
                "state",
                "draft",
                "assignees",
                "milestone",
                "requested_reviewers",
                "requested_teams",
            )
        }
        | {"head": head, "base": object_value(pr.get("base")).get("ref")}
    )
    return Snapshot(
        number=number,
        node_id=string(pr.get("node_id")),
        title=string(pr.get("title")),
        url=string(pr.get("html_url")),
        author=string(author.get("login")),
        author_type=string(author.get("type")),
        state=string(pr.get("state")),
        draft=draft,
        updated_at=timestamp(pr.get("updated_at")).isoformat(),
        head=head,
        base=string(object_value(pr.get("base")).get("ref")),
        labels=labels,
        assignees=tuple(string(object_value(item).get("login")) for item in array(pr.get("assignees"))),
        requested_users=tuple(string(item.get("login")) for item in users),
        requested_teams=tuple(string(item.get("slug")) for item in teams),
        reviews=tuple(reviews),
        checks=tuple(string(item.get("conclusion") or item.get("status")) for item in check_runs)
        + tuple(string(item.get("state")) for item in latest_statuses.values()),
        aggregate=readiness,
        feed=tuple(feeds),
        fingerprint=fingerprint,
        observed_at=now.isoformat(),
    )


@dataclass(frozen=True)
class Receipt:
    operation: str
    identity: str
    actor: str
    kind: str
    at: str
    content_hash: str


@dataclass(frozen=True)
class Intent:
    operation: str
    kind: str
    content_hash: str
    prior_hash: str
    feed_baseline: str | None = None


@dataclass(frozen=True)
class WarningCycle:
    cycle: str
    delivered_at: str
    deadline: str
    initial_operation: str
    final_operation: str | None = None
    milestones: tuple[str, ...] = ()


@dataclass(frozen=True)
class Entry:
    number: int
    node_id: str
    activity_at: str
    observed_at: str
    raw_updated_at: str
    fingerprint: str
    head: str
    labels: tuple[str, ...]
    watermarks: tuple[tuple[str, str], ...]
    external_digest: str = ""
    reopened_at: str | None = None
    receipts: tuple[Receipt, ...] = ()
    pending: Intent | None = None
    warning: WarningCycle | None = None
    neutralize: str | None = None
    last_notice_at: str | None = None


@dataclass(frozen=True)
class Ledger:
    generation: int = 0
    entries: tuple[Entry, ...] = ()
    last_successful_refresh: str | None = None


def stage_intent(*, entry: Entry, intent: Intent) -> Entry:
    if entry.pending is not None and entry.pending != intent:
        raise IncompleteDataError("Unresolved prior write")
    if intent.prior_hash != entry.fingerprint:
        raise IncompleteDataError("Write intent baseline conflict")
    return replace(entry, pending=intent)


def finalize_receipt(*, entry: Entry, receipt: Receipt) -> Entry:
    intent = entry.pending
    if intent is None or (receipt.operation, receipt.kind, receipt.content_hash, receipt.actor) != (
        intent.operation,
        intent.kind,
        intent.content_hash,
        TRUSTED_BOT,
    ):
        raise IncompleteDataError("Receipt does not match pending intent")
    updated = replace(entry, pending=None, receipts=(*entry.receipts, receipt))
    if receipt.operation.startswith("ordinary:"):
        updated = replace(updated, last_notice_at=receipt.at)
    if receipt.operation.startswith("milestone-") and updated.warning:
        kind = receipt.operation.split(":", 1)[0]
        updated = replace(
            updated,
            warning=replace(updated.warning, milestones=tuple(dict.fromkeys((*updated.warning.milestones, kind)))),
        )
    return updated


def recover_receipt(*, intent: Intent, feed: tuple[FeedItem, ...]) -> Receipt | None:
    matches = [
        item
        for item in feed
        if item.actor == TRUSTED_BOT and item.kind == intent.kind and item.content_hash == intent.content_hash
    ]
    matches = list({(item.identity, item.at, item.content_hash): item for item in matches}.values())
    if len(matches) > 1:
        raise IncompleteDataError("Ambiguous write receipts")
    if not matches:
        return None
    item = matches[0]
    return Receipt(
        operation=intent.operation,
        identity=item.identity,
        actor=item.actor,
        kind=item.kind,
        at=item.at,
        content_hash=item.content_hash,
    )


def reconcile_pending(*, snapshot: Snapshot, previous: Entry | None) -> Entry | None:
    if previous is None or previous.pending is None:
        return previous
    feed = snapshot.feed
    if previous.pending.kind in {"labeled", "unlabeled"}:
        intent = previous.pending
        matching = tuple(item for item in feed if item.kind == intent.kind and item.content_hash == intent.content_hash)
        feed = tuple(
            item
            for item in matching
            if item.actor == TRUSTED_BOT
            and feed_digest(tuple(other for other in matching if other.identity != item.identity))
            == intent.feed_baseline
        )
        if matching and not feed:
            raise IncompleteDataError("Label receipt cannot be distinguished from its baseline")
    receipt = recover_receipt(intent=previous.pending, feed=feed)
    if receipt is None:
        return replace(
            previous,
            pending=None,
            warning=None,
            neutralize=previous.warning.cycle if previous.warning else previous.neutralize,
        )
    return finalize_receipt(entry=previous, receipt=receipt)


def feed_digest(feed: tuple[FeedItem, ...]) -> str:
    return digest([asdict(item) for item in sorted(feed, key=lambda item: (item.identity, item.at, item.content_hash))])


def external_feed(*, snapshot: Snapshot, receipts: tuple[Receipt, ...]) -> tuple[FeedItem, ...]:
    owned = {
        (item.identity, item.actor, item.kind, item.at, item.content_hash)
        for item in receipts
        if item.actor == TRUSTED_BOT
    }
    return tuple(
        item
        for item in snapshot.feed
        if (item.identity, item.actor, item.kind, item.at, item.content_hash) not in owned
    )


def activity_digest(*, snapshot: Snapshot, receipts: tuple[Receipt, ...]) -> str:
    latest = {receipt.identity: receipt for receipt in receipts}
    present = {item.identity for item in snapshot.feed}
    missing: list[JsonValue] = [identity for identity in sorted(latest) if identity not in present]
    return digest(
        {"external": feed_digest(external_feed(snapshot=snapshot, receipts=receipts)), "missing_owned": missing}
    )


def observe_activity(*, snapshot: Snapshot, previous: Entry | None) -> Entry:
    external = external_feed(snapshot=snapshot, receipts=previous.receipts if previous else ())
    aggregate = activity_digest(snapshot=snapshot, receipts=previous.receipts if previous else ())
    reopened = max((item.at for item in external if item.kind == "reopened"), default=None)
    if previous is None:
        return Entry(
            number=snapshot.number,
            node_id=snapshot.node_id,
            activity_at=max([snapshot.updated_at, *(item.at for item in snapshot.feed)]),
            observed_at=snapshot.observed_at,
            raw_updated_at=snapshot.updated_at,
            fingerprint=snapshot.fingerprint,
            head=snapshot.head,
            labels=snapshot.labels,
            watermarks=(),
            external_digest=aggregate,
            reopened_at=reopened,
        )
    if previous.number != snapshot.number or previous.node_id != snapshot.node_id:
        raise IncompleteDataError("Ledger PR identity mismatch")
    changed = aggregate != previous.external_digest
    owned_times = {item.at for item in snapshot.feed if item not in external}
    unexplained = (
        previous.fingerprint != snapshot.fingerprint
        or (previous.raw_updated_at != snapshot.updated_at and snapshot.updated_at not in owned_times)
        or (
            previous.labels != snapshot.labels
            and not any(
                item.kind in {"labeled", "unlabeled"} and timestamp(item.at) >= timestamp(previous.observed_at)
                for item in snapshot.feed
                if item not in external
            )
        )
    )
    reset = changed or unexplained or previous.head != snapshot.head
    reopened_now = reopened is not None and (previous.reopened_at is None or reopened > previous.reopened_at)
    activity = max(previous.activity_at, snapshot.observed_at) if reset else previous.activity_at
    if (
        reopened_now
        and reopened is not None
        and previous.head == snapshot.head
        and snapshot.updated_at == reopened
        and max((item.at for item in external), default=None) == reopened
    ):
        activity = max(previous.activity_at, reopened)
    return replace(
        previous,
        activity_at=activity,
        observed_at=snapshot.observed_at,
        raw_updated_at=snapshot.updated_at,
        fingerprint=snapshot.fingerprint,
        head=snapshot.head,
        labels=snapshot.labels,
        watermarks=(),
        external_digest=aggregate,
        reopened_at=reopened,
        warning=None if reset else previous.warning,
        neutralize=previous.warning.cycle if reset and previous.warning else previous.neutralize,
        last_notice_at=None if reopened_now else previous.last_notice_at,
    )


BLOCKER_LABELS = frozenset(
    {"state/blocked", "state/need-decision", "state/need-more-info", "state/needs-human-fix", "state/needs-human-test"}
)
OWNED_LABELS = frozenset({"lifecycle-warning", "lifecycle-approved", "lifecycle-bot"})


def current_reviews(*, snapshot: Snapshot) -> dict[str, str]:
    result: dict[str, str] = {}
    for review in sorted(snapshot.reviews, key=lambda item: (timestamp(item.submitted_at), item.identity)):
        if review.state in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
            result[review.author] = review.state
        elif review.state not in {"COMMENTED", "PENDING"}:
            raise IncompleteDataError("Unknown review state")
    return result


def closure_exemptions(*, snapshot: Snapshot) -> tuple[str, ...]:
    result = []
    if snapshot.author_type == "Bot" or snapshot.author.endswith("[bot]"):
        result.append("bot")
    elif snapshot.author_type != "User":
        raise IncompleteDataError("Unknown PR author type")
    if "keep-open" in snapshot.labels:
        result.append("keep-open")
    if "APPROVED" in current_reviews(snapshot=snapshot).values():
        result.append("approval")
    return tuple(result)


def warning_needed(*, snapshot: Snapshot, entry: Entry, now: datetime) -> bool:
    return (
        snapshot.state == "open"
        and not closure_exemptions(snapshot=snapshot)
        and now >= timestamp(entry.activity_at) + timedelta(days=60)
        and entry.warning is None
    )


@dataclass(frozen=True)
class Classification:
    category: str
    actors: tuple[str, ...]
    action: str
    blockers: tuple[str, ...]
    exemptions: tuple[str, ...]
    ready: bool


def classify(*, snapshot: Snapshot, entry: Entry) -> Classification:
    reviews = current_reviews(snapshot=snapshot)
    exemptions = closure_exemptions(snapshot=snapshot)
    aggregate = snapshot.aggregate
    changes = "CHANGES_REQUESTED" in reviews.values()
    checks = any(state not in {"success", "neutral", "skipped"} for state in snapshot.checks)
    explicit = tuple(sorted(set(snapshot.labels) & BLOCKER_LABELS))
    conflicts = aggregate.mergeable == "CONFLICTING" or aggregate.merge_state == "DIRTY"
    requirements = (
        aggregate.head != snapshot.head
        or aggregate.mergeable != "MERGEABLE"
        or aggregate.merge_state != "CLEAN"
        or aggregate.review_decision not in {None, "APPROVED"}
    )
    blockers = (
        tuple(
            reason
            for reason, present in (
                ("requested changes", changes),
                ("checks pending or failing", checks),
                ("merge conflicts", conflicts),
                ("merge requirements pending or unknown", requirements),
            )
            if present
        )
        + explicit
    )
    ready = "approval" in exemptions and not blockers and not snapshot.draft
    reviewers = snapshot.requested_users + tuple(f"opsmill/{team}" for team in snapshot.requested_teams)
    actors = (snapshot.author,)
    if snapshot.draft:
        action = "finish this draft and mark it ready for review"
    elif changes:
        action = "address the requested changes and request another review"
    elif checks or explicit or conflicts:
        action = "resolve " + ", ".join(
            reason for reason in blockers if reason != "merge requirements pending or unknown"
        )
    elif ready:
        action = "merge this approved pull request"
    elif reviewers and (not requirements or aggregate.review_decision == "REVIEW_REQUIRED"):
        actors, action = reviewers, "review this pull request"
    elif "approval" in exemptions or requirements:
        action = "resolve the outstanding or unknown merge requirements"
    elif reviewers:
        actors, action = reviewers, "review this pull request"
    else:
        action = "request review from a reviewer or team"
    category = "waiting for review" if actors == reviewers and reviewers else "waiting for author"
    if ready:
        category = "ready to merge"
    if blockers:
        category = "blocked"
    if snapshot.draft:
        category = "draft"
    if entry.warning:
        category = "closing soon"
    if "bot" in exemptions:
        category, actors, action = "excluded bot", (), "excluded from lifecycle reminders"
    return Classification(
        category=category, actors=actors, action=action, blockers=blockers, exemptions=exemptions, ready=ready
    )


def next_notice(*, snapshot: Snapshot, entry: Entry, now: datetime) -> str | None:
    if entry.neutralize:
        return "cancel"
    if snapshot.state != "open" or "bot" in closure_exemptions(snapshot=snapshot):
        return None
    if warning_needed(snapshot=snapshot, entry=entry, now=now):
        return "warning"
    warning = entry.warning
    if warning:
        if not warning.final_operation or closure_exemptions(snapshot=snapshot) or now >= timestamp(warning.deadline):
            return None
        midnight = timestamp(warning.delivered_at).replace(hour=0, minute=0, second=0, microsecond=0)
        if now >= midnight + timedelta(days=13):
            kind = "milestone-1"
        elif now >= midnight + timedelta(days=7):
            kind = "milestone-7"
        else:
            kind = None
        return None if kind in warning.milestones else kind
    baseline = max(timestamp(entry.activity_at), timestamp(entry.last_notice_at or entry.activity_at))
    return "ordinary" if now >= baseline + timedelta(days=7) else None


def notice_body(
    *, entry: Entry, operation: str, kind: str, cycle: str = "", deadline: str = "", snapshot: Snapshot | None = None
) -> str:
    marker = {
        "repository": ALLOWED_REPOSITORY,
        "pr": entry.number,
        "operation": operation,
        "kind": kind,
        "cycle": cycle,
        "activity": entry.activity_at,
        "prior_hash": entry.fingerprint,
    }
    text = {
        "warning": (
            "This pull request has been inactive for at least 60 days. "
            "A 14-day closure warning is being prepared; the confirmed deadline will appear here."
        ),
        "deadline": (
            f"This pull request is inactive and may be closed after {deadline} UTC. "
            "Comment or update the PR to keep it active; maintainers can apply keep-open."
        ),
        "cancel": "The previous closure warning is canceled. That deadline no longer applies.",
    }.get(
        kind,
        f"This pull request remains inactive and may be closed after {deadline} UTC. "
        "Comment or update it to keep it active; maintainers can apply keep-open.",
    )
    if snapshot is not None and kind == "ordinary":
        routing = classify(snapshot=snapshot, entry=entry)
        text = ", ".join(f"@{actor}" for actor in routing.actors) + ": please " + routing.action + "."
    elif snapshot is not None and kind in {"warning", "deadline", "milestone-7", "milestone-1"}:
        actors = dict.fromkeys(
            (snapshot.author, *snapshot.requested_users, *(f"opsmill/{team}" for team in snapshot.requested_teams))
        )
        text = ", ".join(f"@{actor}" for actor in actors) + ": " + text
    return (
        text + "\n\n<!-- infrahub-pr-lifecycle:v1 " + json.dumps(marker, sort_keys=True, separators=(",", ":")) + " -->"
    )


def closure_due(*, snapshot: Snapshot, entry: Entry, now: datetime) -> bool:
    warning = entry.warning
    if (
        snapshot.state != "open"
        or closure_exemptions(snapshot=snapshot)
        or entry.pending
        or warning is None
        or not warning.final_operation
    ):
        return False
    delivered, deadline = timestamp(warning.delivered_at), timestamp(warning.deadline)
    if (
        deadline != delivered + timedelta(days=14)
        or now < deadline
        or delivered < timestamp(entry.activity_at) + timedelta(days=60)
    ):
        return False
    expected = digest(
        notice_body(
            entry=entry,
            operation=warning.final_operation,
            kind="deadline",
            cycle=warning.cycle,
            deadline=warning.deadline,
            snapshot=snapshot,
        )
    )
    initial = next((receipt for receipt in entry.receipts if receipt.operation == warning.initial_operation), None)
    final = next((receipt for receipt in entry.receipts if receipt.operation == warning.final_operation), None)
    if initial is None or final is None or initial.identity != final.identity or final.content_hash != expected:
        return False
    owned = {
        (item.identity, item.actor, item.kind, item.at, item.content_hash)
        for item in entry.receipts
        if item.actor == TRUSTED_BOT
    }
    if any(
        timestamp(item.at) > delivered
        and (item.identity, item.actor, item.kind, item.at, item.content_hash) not in owned
        for item in snapshot.feed
    ):
        return False
    return any(
        item.identity == final.identity
        and item.actor == TRUSTED_BOT
        and item.kind == "comment"
        and item.content_hash == expected
        and item.at == final.at
        and timestamp(item.created_at or item.at) == delivered
        for item in snapshot.feed
    )


def warning_confirmed(*, snapshot: Snapshot, entry: Entry) -> bool:
    warning = entry.warning
    if warning is None or not warning.final_operation:
        return False
    initial = next((item for item in entry.receipts if item.operation == warning.initial_operation), None)
    final = next((item for item in entry.receipts if item.operation == warning.final_operation), None)
    expected = digest(
        notice_body(
            entry=entry,
            operation=warning.final_operation,
            kind="deadline",
            cycle=warning.cycle,
            deadline=warning.deadline,
            snapshot=snapshot,
        )
    )
    return bool(
        initial
        and final
        and initial.identity == final.identity
        and final.content_hash == expected
        and any(
            item.identity == final.identity
            and item.actor == TRUSTED_BOT
            and item.kind == "comment"
            and item.content_hash == expected
            and item.at == final.at
            and timestamp(item.created_at or item.at) == timestamp(warning.delivered_at)
            for item in snapshot.feed
        )
    )


def encode_ledger(*, ledger: Ledger, visible: str = "") -> str:
    payload = {"version": 1, "repository": ALLOWED_REPOSITORY, **asdict(ledger)}
    encoded = base64.b64encode(zlib.compress(json.dumps(payload, separators=(",", ":")).encode())).decode()
    body = f"{visible}\n{DASHBOARD_MARKER}\n{STATE_PREFIX}{encoded} -->"
    if len(body) > MAX_BODY:
        raise IncompleteDataError("Dashboard exceeds 60000 characters")
    return body


def decode_ledger(*, body: str) -> Ledger:  # noqa: PLR0914 - Validate the entire persisted record at one boundary.
    if body.count(STATE_PREFIX) != 1:
        raise IncompleteDataError("Missing or ambiguous ledger")
    encoded = body.split(STATE_PREFIX, 1)[1].split(" -->", 1)[0]
    try:
        compressed = base64.b64decode(encoded, validate=True)
        decompressor = zlib.decompressobj()
        raw = decompressor.decompress(compressed, MAX_STATE + 1)
        if len(raw) > MAX_STATE or not decompressor.eof:
            raise IncompleteDataError("Ledger decompression limit exceeded")
        value = object_value(json.loads(raw))
    except (ValueError, zlib.error, binascii.Error) as exc:
        raise IncompleteDataError("Corrupt ledger") from exc
    if value.get("version") != 1 or value.get("repository") != ALLOWED_REPOSITORY:
        raise IncompleteDataError("Unsupported ledger version or repository")
    generation = integer(value.get("generation"))
    if generation < 0:
        raise IncompleteDataError("Invalid ledger generation")
    entries: list[Entry] = []
    for raw_entry in array(value.get("entries")):
        item = object_value(raw_entry)
        receipts = []
        for raw_receipt in array(item.get("receipts")):
            receipt = object_value(raw_receipt)
            receipts.append(
                Receipt(
                    operation=string(receipt.get("operation")),
                    identity=string(receipt.get("identity")),
                    actor=string(receipt.get("actor")),
                    kind=string(receipt.get("kind")),
                    at=timestamp(receipt.get("at")).isoformat(),
                    content_hash=string(receipt.get("content_hash")),
                )
            )
        pending = None
        if item.get("pending") is not None:
            intent = object_value(item["pending"])
            pending = Intent(
                operation=string(intent.get("operation")),
                kind=string(intent.get("kind")),
                content_hash=string(intent.get("content_hash")),
                prior_hash=string(intent.get("prior_hash")),
                feed_baseline=None if intent.get("feed_baseline") is None else string(intent.get("feed_baseline")),
            )
        marks = []
        for raw_mark in array(item.get("watermarks")):
            mark = array(raw_mark)
            if len(mark) != WATERMARK_FIELDS:
                raise IncompleteDataError("Invalid feed watermark")
            marks.append((string(mark[0]), string(mark[1])))
        warning = None
        if item.get("warning") is not None:
            raw_warning = object_value(item["warning"])
            final_operation = raw_warning.get("final_operation")
            warning = WarningCycle(
                cycle=string(raw_warning.get("cycle")),
                delivered_at=timestamp(raw_warning.get("delivered_at")).isoformat(),
                deadline=timestamp(raw_warning.get("deadline")).isoformat(),
                initial_operation=string(raw_warning.get("initial_operation")),
                final_operation=None if final_operation is None else string(final_operation),
                milestones=tuple(string(mark) for mark in array(raw_warning.get("milestones", []))),
            )
        notice = item.get("last_notice_at")
        entries.append(
            Entry(
                number=integer(item.get("number")),
                node_id=string(item.get("node_id")),
                activity_at=timestamp(item.get("activity_at")).isoformat(),
                observed_at=timestamp(item.get("observed_at")).isoformat(),
                raw_updated_at=timestamp(item.get("raw_updated_at")).isoformat(),
                fingerprint=string(item.get("fingerprint")),
                head=string(item.get("head")),
                labels=tuple(string(label) for label in array(item.get("labels"))),
                watermarks=tuple(marks),
                external_digest=string(item.get("external_digest", "")),
                reopened_at=None if item.get("reopened_at") is None else timestamp(item.get("reopened_at")).isoformat(),
                receipts=tuple(receipts),
                pending=pending,
                warning=warning,
                neutralize=None if item.get("neutralize") is None else string(item.get("neutralize")),
                last_notice_at=None if notice is None else timestamp(notice).isoformat(),
            )
        )
    if len({item.number for item in entries}) != len(entries):
        raise IncompleteDataError("Duplicate ledger PR")
    refreshed = value.get("last_successful_refresh")
    return Ledger(
        generation=generation,
        entries=tuple(entries),
        last_successful_refresh=None if refreshed is None else timestamp(refreshed).isoformat(),
    )


def verify_generation(*, expected_body: str, current_body: str) -> None:
    if (
        expected_body != current_body
        or decode_ledger(body=expected_body).generation != decode_ledger(body=current_body).generation
    ):
        raise IncompleteDataError("Ledger generation or content conflict")


def prune_ledger(
    *,
    ledger: Ledger,
    confirmed_closed: frozenset[int],
    gates_cleaned: frozenset[int],
    snapshots: tuple[Snapshot, ...] = (),
) -> Ledger:
    current = {value.number: value for value in snapshots}
    entries = []
    for original in ledger.entries:
        entry = original
        if entry.number in confirmed_closed & gates_cleaned and entry.pending is None:
            continue
        if entry.number in current and entry.pending is None:
            receipts = tuple(
                receipt
                for receipt in entry.receipts
                if entry.warning is not None and timestamp(receipt.at) >= timestamp(entry.warning.delivered_at)
            )
            entry = replace(
                entry,
                receipts=receipts,
                external_digest=activity_digest(snapshot=current[entry.number], receipts=receipts),
            )
        entries.append(entry)
    return replace(ledger, entries=tuple(entries))


def discover_dashboard(*, transport: ReadTransport, adopted_issue: int | None = None) -> tuple[int, str] | None:
    matches = []
    for issue in pages(
        transport=transport, path=f"/repos/{ALLOWED_REPOSITORY}/issues?state=all&creator=github-actions%5Bbot%5D"
    ):
        body = issue.get("body")
        if "pull_request" in issue or not isinstance(body, str) or DASHBOARD_MARKER not in body:
            continue
        author = object_value(issue.get("user"))
        if author.get("login") != TRUSTED_BOT or author.get("type") != "Bot":
            raise IncompleteDataError("Dashboard marker has untrusted author")
        matches.append((integer(issue.get("number")), body))
    if adopted_issue is not None:
        if adopted_issue < 1:
            raise IncompleteDataError("Invalid adopted dashboard number")
        issue = object_value(transport.get_json(path=f"/repos/{ALLOWED_REPOSITORY}/issues/{adopted_issue}"))
        if "pull_request" in issue or integer(issue.get("number")) != adopted_issue:
            raise IncompleteDataError("Adopted dashboard must be an issue")
        body = string(issue.get("body") or "")
        if not any(number == adopted_issue for number, _ in matches):
            matches.append((adopted_issue, body))
    if len(matches) > 1:
        raise IncompleteDataError(f"Multiple dashboards: {[number for number, _ in matches]}")
    return matches[0] if matches else None


@dataclass(frozen=True)
class CacheRecord:
    identity: int
    created_at: str
    last_accessed_at: str
    size_in_bytes: int


def read_cache(*, transport: ReadTransport, ref: str) -> CacheRecord | None:
    if not ref.startswith("refs/heads/"):
        raise IncompleteDataError("Cache ref must identify a branch")
    query = urllib.parse.urlencode({"key": "_state", "ref": ref})
    matches = [
        item
        for item in pages(
            transport=transport, path=f"/repos/{ALLOWED_REPOSITORY}/actions/caches?{query}", key="actions_caches"
        )
        if item.get("key") == "_state" and item.get("ref") == ref
    ]
    if len(matches) > 1:
        raise IncompleteDataError("Ambiguous exact _state cache entries")
    if not matches:
        return None
    item = matches[0]
    return CacheRecord(
        identity=integer(item.get("id")),
        created_at=timestamp(item.get("created_at")).isoformat(),
        last_accessed_at=timestamp(item.get("last_accessed_at")).isoformat(),
        size_in_bytes=integer(item.get("size_in_bytes")),
    )


def verify_candidates(*, transport: ReadTransport, candidates: tuple[int, ...]) -> tuple[int, ...]:
    remaining = []
    for number in candidates:
        pr = object_value(transport.get_json(path=f"/repos/{ALLOWED_REPOSITORY}/pulls/{number}"))
        if integer(pr.get("number")) != number or pr.get("state") not in ("open", "closed"):
            raise IncompleteDataError("Incomplete candidate post-verification")
        if pr["state"] == "open":
            remaining.append(number)
    return tuple(remaining)


def continuation(
    *,
    pass_number: int,
    before: CacheRecord | None,
    after: CacheRecord | None,
    previous: tuple[int, ...],
    remaining: tuple[int, ...],
) -> bool:
    if not 1 <= pass_number <= MAX_PASSES or not set(remaining).issubset(previous):
        raise IncompleteDataError("Invalid continuation evidence")
    if not remaining:
        return False
    if pass_number == MAX_PASSES:
        raise IncompleteDataError(f"Four-pass bound exhausted; deferred PRs: {remaining}")
    if before is not None and after is not None and before.identity == after.identity:
        raise IncompleteDataError("Exact _state cache unchanged with candidates remaining")
    # A cleared old scan permits one fresh sweep of candidates skipped by cached IDs.
    if set(remaining) == set(previous) and after is None and before is None:
        raise IncompleteDataError(f"No candidate or continuation progress; deferred PRs: {remaining}")
    return True


class BudgetedReads:
    def __init__(self, *, transport: ReadTransport, budget: int) -> None:
        self.transport = transport
        self.budget = budget
        self.requests = 0

    def consume(self) -> None:
        if self.requests >= self.budget:
            raise IncompleteDataError("Observation request budget exhausted")
        self.requests += 1

    def get_json(self, *, path: str) -> JsonValue:
        self.consume()
        return self.transport.get_json(path=path)

    def query(self, *, number: int) -> JsonValue:
        self.consume()
        return self.transport.query(number=number)


def preflight(*, transport: BudgetedReads, human_count: int) -> None:
    resources = object_value(object_value(transport.get_json(path="/rate_limit")).get("resources"))
    core = integer(object_value(resources.get("core")).get("remaining"))
    graphql = integer(object_value(resources.get("graphql")).get("remaining"))
    if core < human_count * REST_READS_PER_PR + QUOTA_RESERVE or graphql < human_count + QUOTA_RESERVE:
        raise IncompleteDataError(f"Insufficient API quota for {human_count} human PRs and verification reserve")
    if transport.budget - transport.requests < human_count * (REST_READS_PER_PR + 1) + QUOTA_RESERVE:
        raise IncompleteDataError("Insufficient request budget for full observation")


@dataclass(frozen=True)
class Proposal:
    number: int
    classification: Classification
    activity_at: str
    notice: str | None
    deadline: str | None
    closure_due: bool


@dataclass(frozen=True)
class ExcludedBot:
    number: int
    title: str
    author: str


@dataclass(frozen=True)
class ObservationReport:
    version: int
    repository: str
    mode: Mode
    observed_at: str
    complete: bool
    closure_ready: bool
    errors: tuple[str, ...]
    inventory: tuple[Snapshot, ...] = ()
    excluded_bots: tuple[int, ...] = ()
    inventory_count: int = 0
    evaluated_count: int = 0
    requests: int = 0
    proposals: tuple[Proposal, ...] = ()
    proposed_counts: tuple[tuple[str, int], ...] = ()
    bot_rows: tuple[ExcludedBot, ...] = ()
    dashboard_preview: str | None = None


def guard_repository(repository: str) -> None:
    if repository != ALLOWED_REPOSITORY:
        raise ValueError(f"Repository must be {ALLOWED_REPOSITORY}")


def observe(  # noqa: PLR0914, PLR0915 - One boundary reports inventory and capacity failures together.
    *,
    repository: str,
    transport: ReadTransport | None,
    clock: Callable[[], datetime] = utc_now,
    budget: int = DEFAULT_BUDGET,
    adopted_issue: int | None = None,
) -> ObservationReport:
    guard_repository(repository)
    now = clock()
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Clock must return a timezone-aware timestamp")
    if budget < 1:
        raise ValueError("Request budget must be positive")
    if transport is None:
        transport = GitHubClient(token=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", ""), budget=budget)
    reads = BudgetedReads(transport=transport, budget=budget)
    identity = object_value(reads.get_json(path=f"/repos/{repository}"))
    if identity.get("full_name") != repository:
        raise ValueError("GitHub repository identity does not match the requested repository")
    snapshots: list[Snapshot] = []
    bots: list[int] = []
    errors: list[str] = []
    inventory_count = 0
    proposals: list[Proposal] = []
    bot_rows: list[ExcludedBot] = []
    observed_entries: list[Entry] = []
    ledger = Ledger()
    try:
        dashboard = discover_dashboard(transport=reads, adopted_issue=adopted_issue)
        ledger = decode_ledger(body=dashboard[1]) if dashboard and STATE_PREFIX in dashboard[1] else Ledger()
        if dashboard and STATE_PREFIX not in dashboard[1] and adopted_issue is None:
            raise IncompleteDataError("Missing dashboard ledger")
        inventory = pages(transport=reads, path=f"/repos/{repository}/pulls?state=open")
        inventory_count = len(inventory)
        humans = []
        for pr in inventory:
            number = integer(pr.get("number"))
            author = object_value(pr.get("user"))
            login = string(author.get("login"))
            kind = string(author.get("type"))
            if kind == "Bot" or login.endswith("[bot]"):
                bots.append(number)
                bot_rows.append(ExcludedBot(number=number, title=string(pr.get("title")), author=login))
            elif kind == "User":
                humans.append(number)
            else:
                raise IncompleteDataError("Unknown PR author type")
        preflight(transport=reads, human_count=len(humans))
        snapshots.extend(collect_snapshot(transport=reads, number=number, now=now) for number in humans)
        entries = {entry.number: entry for entry in ledger.entries}
        for value in snapshots:
            entry = observe_activity(
                snapshot=value, previous=reconcile_pending(snapshot=value, previous=entries.get(value.number))
            )
            exemptions = closure_exemptions(snapshot=value)
            if entry.warning and (exemptions or not entry.warning.final_operation):
                entry = replace(entry, neutralize=entry.warning.cycle, warning=None)
            observed_entries.append(entry)
            proposals.append(
                Proposal(
                    number=value.number,
                    classification=classify(snapshot=value, entry=entry),
                    activity_at=entry.activity_at,
                    notice=next_notice(snapshot=value, entry=entry, now=now),
                    deadline=entry.warning.deadline if entry.warning else None,
                    closure_due=closure_due(snapshot=value, entry=entry, now=now),
                )
            )
    except IncompleteDataError as exc:
        errors.append(str(exc))
    report = ObservationReport(
        version=1,
        repository=repository,
        mode=Mode.OBSERVE,
        observed_at=now.astimezone(UTC).isoformat(),
        complete=not errors,
        closure_ready=False,
        errors=tuple(errors),
        inventory=tuple(snapshots),
        excluded_bots=tuple(bots),
        inventory_count=inventory_count,
        evaluated_count=len(snapshots) + len(bots),
        requests=transport.requests if isinstance(transport, GitHubClient) else reads.requests,
        proposals=tuple(proposals),
        bot_rows=tuple(bot_rows),
        proposed_counts=tuple(
            (kind, sum(proposal.notice == kind for proposal in proposals))
            for kind in ("ordinary", "warning", "cancel", "milestone-7", "milestone-1")
        ),
    )

    if report.complete:
        preview = None
        try:
            observed_numbers = {entry.number for entry in observed_entries}
            preview_ledger = replace(
                ledger,
                entries=(
                    *(entry for entry in ledger.entries if entry.number not in observed_numbers),
                    *observed_entries,
                ),
            )
            preview = render_dashboard(report=report, ledger=preview_ledger, preview=True, include_state=False)
            render_dashboard(report=report, ledger=preview_ledger)
        except IncompleteDataError as exc:
            return replace(report, complete=False, errors=(str(exc),), dashboard_preview=preview)
        report = replace(report, dashboard_preview=preview)
    return report


def dashboard_text(value: str) -> str:
    escaped = html.escape(" ".join(value.split()), quote=True)
    return re.sub(r"([\\`*_{}\[\]()#|@~])", lambda match: f"&#{ord(match[0])};", escaped)


def dashboard_notice(*, entry: Entry, proposal: Proposal, now: datetime) -> str:  # noqa: PLR0911 - Each delivery state has distinct text.
    if entry.pending or entry.neutralize:
        return "Reconciliation required; delivery unconfirmed"
    warning = entry.warning
    if warning:
        if not warning.final_operation:
            return "Warning delivery unconfirmed"
        if now >= timestamp(warning.deadline):
            return (
                "Closure due; eligibility must be rechecked"
                if proposal.closure_due
                else "Closure requires verification"
            )
        midnight = timestamp(warning.delivered_at).replace(hour=0, minute=0, second=0, microsecond=0)
        candidates = [("milestone-7", midnight + timedelta(days=7)), ("milestone-1", midnight + timedelta(days=13))]
        if proposal.notice:
            return f"{proposal.notice} due now"
        future = [(kind, at) for kind, at in candidates if kind not in warning.milestones and at > now]
        return f"{future[0][0]}: {future[0][1].isoformat()}" if future else "No further notice before deadline"
    if proposal.notice == "warning":
        return "Initial warning due; deadline unset"
    ordinary = max(timestamp(entry.activity_at), timestamp(entry.last_notice_at or entry.activity_at)) + timedelta(
        days=7
    )
    if ordinary <= now:
        return "Reminder due"
    if proposal.classification.exemptions:
        return f"Reminder: {ordinary.isoformat()}"
    warning_at = timestamp(entry.activity_at) + timedelta(days=60)
    kind, at = ("Initial warning", warning_at) if warning_at <= ordinary else ("Reminder", ordinary)
    return f"{kind}: {at.isoformat()}"


def render_dashboard(  # noqa: PLR0914 - One row combines the required presentation fields.
    *, report: ObservationReport, ledger: Ledger, preview: bool = False, include_state: bool = True
) -> str:
    if not report.complete or len(report.proposals) != len(report.inventory):
        raise IncompleteDataError("Cannot render incomplete dashboard")
    link_origin = "https://github.com" if preview else ""
    entries = {entry.number: entry for entry in ledger.entries}
    proposals = {proposal.number: proposal for proposal in report.proposals}
    now = timestamp(report.observed_at)
    groups = (
        ("ready to merge", "Ready to merge"),
        ("waiting for review", "Waiting for review"),
        ("waiting for author", "Waiting for author / Needs reviewer"),
        ("blocked", "Blocked"),
        ("draft", "Drafts"),
        ("closing soon", "Closing soon"),
    )
    lines = [
        "# PR lifecycle dashboard",
        "",
        f"Last successful refresh: {ledger.last_successful_refresh or 'never'}",
        "",
        f"{'Observation preview' if preview else 'Snapshot'}: {report.observed_at} (UTC)",
        "",
        f"Open PRs: {report.inventory_count}; human: {len(report.inventory)}; excluded bots: {len(report.bot_rows)}.",
        "",
        "Days inactive means elapsed whole days since observed non-lifecycle activity, not time waiting for review.",
        "",
    ]
    for category, heading in groups:
        values = [value for value in report.inventory if proposals[value.number].classification.category == category]
        lines.extend([f"## {heading} ({len(values)})", ""])
        if not values:
            lines.extend(["None.", ""])
            continue
        lines.extend(
            [
                "| PR / author | Next actor / action | Days inactive | Blockers / closure exemptions | Next notice / deadline (UTC) |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for value in sorted(values, key=lambda item: item.number):
            proposal = proposals[value.number]
            entry = entries.get(value.number) or observe_activity(snapshot=value, previous=None)
            classification = proposal.classification
            days = max(0, (now - timestamp(proposal.activity_at)).days)
            reasons = f"{', '.join(classification.blockers) or '—'} / {', '.join(classification.exemptions) or '—'}"
            notice = dashboard_notice(entry=entry, proposal=proposal, now=now)
            if proposal.deadline:
                notice += f"; closure deadline: {proposal.deadline}"
            action = {
                "finish this draft and mark it ready for review": "Finish draft; ready; request review",
                "address the requested changes and request another review": "Address feedback; request review",
                "merge this approved pull request": "Merge",
                "review this pull request": "Review",
                "request review from a reviewer or team": "Request person/team review",
                "resolve the outstanding or unknown merge requirements": "Resolve merge requirements",
            }.get(classification.action, "Resolve listed blockers")
            cells = [
                f"[#{value.number}]({link_origin}/{ALLOWED_REPOSITORY}/pull/{value.number}) "
                f"{dashboard_text(value.title)} / {dashboard_text(value.author)}",
                dashboard_text(f"{', '.join(classification.actors)}: {action}"),
                str(days),
                dashboard_text(reasons),
                dashboard_text(notice),
            ]
            lines.append("|" + "|".join(cells) + "|")
        lines.append("")
    lines.extend([f"## Bot-authored PRs ({len(report.bot_rows)})", "", "Excluded from reminders and cleanup.", ""])
    lines.extend(
        f"- [#{bot.number}]({link_origin}/{ALLOWED_REPOSITORY}/pull/{bot.number}) {dashboard_text(bot.title)} / {dashboard_text(bot.author)}"
        for bot in sorted(report.bot_rows, key=lambda item: item.number)
    )
    visible = "\n".join(lines)
    return encode_ledger(ledger=ledger, visible=visible) if include_state else visible


@runtime_checkable
class WriteTransport(ReadTransport, Protocol):
    def write_json(self, *, method: str, path: str, payload: JsonValue, mode: Mode) -> JsonValue: ...


def validate_write(*, method: str, path: str, payload: JsonValue, mode: Mode) -> None:
    if mode != Mode.APPLY:
        raise IncompleteDataError("Mutation requires explicit apply mode")
    root = f"/repos/{ALLOWED_REPOSITORY}"
    suffix = path.removeprefix(root)
    if not path.startswith(root + "/"):
        raise IncompleteDataError("Write outside allowed repository")
    data = object_value(payload)
    allowed = False
    if (method == "POST" and re.fullmatch(r"/issues/\d+/comments", suffix)) or (
        method == "PATCH" and re.fullmatch(r"/issues/comments/\d+", suffix)
    ):
        allowed = set(data) == {"body"} and "<!-- infrahub-pr-lifecycle:v1 " in string(data["body"])
    elif method in {"POST", "PATCH"} and (suffix == "/issues" or re.fullmatch(r"/issues/\d+", suffix)):
        allowed = set(data) <= {"body", "title"} and DASHBOARD_MARKER in string(data.get("body"))
    elif method == "DELETE" and re.fullmatch(r"/labels/lifecycle-close-[1-9]\d*-[1-9]\d*", suffix):
        allowed = not data
    elif method == "POST" and suffix == "/labels":
        allowed = set(data) <= {"name", "color", "description"} and owned_label(string(data.get("name")))
    elif method == "POST" and re.fullmatch(r"/issues/\d+/labels", suffix):
        allowed = set(data) == {"labels"} and all(owned_label(string(label)) for label in array(data["labels"]))
    elif method == "DELETE" and re.fullmatch(r"/issues/\d+/labels/[^/]+", suffix):
        allowed = not data and owned_label(urllib.parse.unquote(suffix.rsplit("/", 1)[1]))
    if not allowed:
        raise IncompleteDataError("Unsupported lifecycle mutation")


def owned_label(label: str) -> bool:
    return label in OWNED_LABELS or bool(re.fullmatch(r"lifecycle-close-[1-9]\d*-[1-9]\d*", label))


def gate_label(*, run_id: str, attempt: str) -> str:
    label = f"lifecycle-close-{run_id}-{attempt}"
    if not owned_label(label):
        raise IncompleteDataError("Invalid run or attempt identity")
    return label


class Lifecycle:
    def __init__(
        self,
        *,
        transport: WriteTransport,
        clock: Callable[[], datetime],
        run_id: str,
        attempt: str,
        adopted_issue: int | None = None,
    ) -> None:
        self.adopted_issue = adopted_issue
        self.transport = transport
        self.clock = clock
        self.gate = gate_label(run_id=run_id, attempt=attempt)
        self.dashboard: tuple[int, str] | None = None
        self.ledger = Ledger()
        self.snapshots: dict[int, Snapshot] = {}
        self.confirmed_operations: set[str] = set()

    def load(self) -> None:
        identity = object_value(self.transport.get_json(path=f"/repos/{ALLOWED_REPOSITORY}"))
        if identity.get("full_name") != ALLOWED_REPOSITORY:
            raise IncompleteDataError("Repository identity mismatch")
        self.dashboard = discover_dashboard(transport=self.transport, adopted_issue=self.adopted_issue)
        if self.dashboard and STATE_PREFIX in self.dashboard[1]:
            self.ledger = decode_ledger(body=self.dashboard[1])
        elif self.dashboard and self.adopted_issue is None:
            raise IncompleteDataError("Missing dashboard ledger")

    def persist(self, *, entry: Entry | None = None, visible: str | None = None, ledger: Ledger | None = None) -> None:
        if entry is not None:
            self.ledger = replace(
                self.ledger, entries=(*(item for item in self.ledger.entries if item.number != entry.number), entry)
            )
        updated = replace(ledger or self.ledger, generation=self.ledger.generation + 1)
        if visible is None:
            visible = (
                self.dashboard[1].split(DASHBOARD_MARKER, 1)[0].rstrip()
                if self.dashboard
                else "PR lifecycle dashboard\n\nNo successful refresh yet."
            )
        body = encode_ledger(ledger=updated, visible=visible)
        if (
            self.dashboard
            and encode_ledger(ledger=replace(updated, generation=self.ledger.generation), visible=visible)
            == self.dashboard[1]
        ):
            return
        root = f"/repos/{ALLOWED_REPOSITORY}/issues"
        if self.dashboard:
            number, expected = self.dashboard
            current = object_value(self.transport.get_json(path=f"{root}/{number}"))
            current_body = string(current.get("body") or "")
            if STATE_PREFIX in expected:
                verify_generation(expected_body=expected, current_body=current_body)
            elif current_body != expected:
                raise IncompleteDataError("Adopted dashboard changed before persistence")
            self.transport.write_json(method="PATCH", path=f"{root}/{number}", payload={"body": body}, mode=Mode.APPLY)
        else:
            try:
                response = object_value(
                    self.transport.write_json(
                        method="POST",
                        path=root,
                        payload={"title": "PR lifecycle dashboard", "body": body},
                        mode=Mode.APPLY,
                    )
                )
                number = integer(response.get("number"))
            except IncompleteDataError:
                found = discover_dashboard(transport=self.transport)
                if found is None or found[1] != body:
                    raise
                number = found[0]
        self.dashboard = (number, body)
        self.ledger = updated

    def entry(self, number: int) -> Entry | None:
        return next((item for item in self.ledger.entries if item.number == number), None)

    def refresh(self, number: int) -> tuple[Snapshot, Entry]:
        value = collect_snapshot(transport=self.transport, number=number, now=self.clock())
        prior = self.entry(number)
        prior_operations = {receipt.operation for receipt in prior.receipts} if prior else set()
        prior = reconcile_pending(snapshot=value, previous=prior)
        if prior:
            self.confirmed_operations.update(
                receipt.operation for receipt in prior.receipts if receipt.operation not in prior_operations
            )
        entry = observe_activity(snapshot=value, previous=prior)
        self.snapshots[number] = value
        self.persist(entry=entry)
        return value, entry

    def comment(
        self,
        *,
        number: int,
        operation: str,
        kind: str,
        cycle: str = "",
        deadline: str = "",
        identity: str | None = None,
    ) -> Receipt:
        value, entry = self.refresh(number)
        if value.state != "open":
            raise IncompleteDataError("PR closed before notice delivery")
        if kind in {"warning", "deadline", "milestone-7", "milestone-1"} and closure_exemptions(snapshot=value):
            raise IncompleteDataError("PR became exempt before warning delivery")
        if kind == "warning" and not warning_needed(snapshot=value, entry=entry, now=self.clock()):
            raise IncompleteDataError("Activity changed before initial warning")
        if kind == "deadline" and (
            entry.warning is None
            or entry.warning.cycle != cycle
            or timestamp(entry.activity_at) + timedelta(days=60) > self.clock()
        ):
            raise IncompleteDataError("Activity canceled deadline finalization")
        if (
            kind in {"ordinary", "milestone-7", "milestone-1"}
            and next_notice(snapshot=value, entry=entry, now=self.clock()) != kind
        ):
            raise IncompleteDataError("Reminder eligibility changed before delivery")
        body = notice_body(entry=entry, operation=operation, kind=kind, cycle=cycle, deadline=deadline, snapshot=value)
        intent = Intent(operation=operation, kind="comment", content_hash=digest(body), prior_hash=entry.fingerprint)
        if previous := next((item for item in entry.receipts if item.operation == operation), None):
            return previous
        entry = stage_intent(entry=entry, intent=intent)
        self.persist(entry=entry)
        root = f"/repos/{ALLOWED_REPOSITORY}/issues"
        path = f"{root}/comments/{identity.split(':')[-1]}" if identity else f"{root}/{number}/comments"
        try:
            raw = object_value(
                self.transport.write_json(
                    method="PATCH" if identity else "POST", path=path, payload={"body": body}, mode=Mode.APPLY
                )
            )
            actor = object_value(raw.get("user"))
            if actor.get("login") != TRUSTED_BOT or actor.get("type") != "Bot" or raw.get("body") != body:
                raise IncompleteDataError("Untrusted comment receipt")
            receipt = Receipt(
                operation=operation,
                identity=f"comment:{integer(raw.get('id'))}",
                actor=TRUSTED_BOT,
                kind="comment",
                at=timestamp(raw.get("updated_at") or raw.get("created_at")).isoformat(),
                content_hash=digest(body),
            )
        except IncompleteDataError:
            current = collect_snapshot(transport=self.transport, number=number, now=self.clock())
            recovered = recover_receipt(intent=intent, feed=current.feed)
            if recovered is None:
                raise
            receipt = recovered
        self.confirmed_operations.add(receipt.operation)
        self.persist(entry=finalize_receipt(entry=entry, receipt=receipt))
        self.refresh(number)
        return receipt

    def label(self, *, number: int, label: str, present: bool) -> None:
        if not owned_label(label):
            raise IncompleteDataError("Cannot mutate manually owned label")
        value, entry = self.refresh(number)
        if (label in value.labels) == present:
            return
        if (
            present
            and label.startswith("lifecycle-close-")
            and not closure_due(snapshot=value, entry=entry, now=self.clock())
        ):
            raise IncompleteDataError("Closure eligibility changed before gate write")
        kind = "labeled" if present else "unlabeled"
        intent = Intent(
            operation=f"{self.gate}:{label}:{kind}:{entry.observed_at}",
            kind=kind,
            content_hash=digest({"event": kind, "label": label}),
            prior_hash=entry.fingerprint,
            feed_baseline=feed_digest(
                tuple(
                    item
                    for item in value.feed
                    if item.kind == kind and item.content_hash == digest({"event": kind, "label": label})
                )
            ),
        )
        entry = stage_intent(entry=entry, intent=intent)
        self.persist(entry=entry)
        root = f"/repos/{ALLOWED_REPOSITORY}/issues/{number}/labels"
        try:
            self.transport.write_json(
                method="POST" if present else "DELETE",
                path=root if present else f"{root}/{urllib.parse.quote(label, safe='')}",
                payload={"labels": [label]} if present else {},
                mode=Mode.APPLY,
            )
        except IncompleteDataError:
            current, _ = self.refresh(number)
            if (label in current.labels) != present:
                raise
            return
        current, _ = self.refresh(number)
        if (label in current.labels) != present:
            raise IncompleteDataError("Label mutation was not confirmed")

    def ensure_labels(self, *, names: frozenset[str] = OWNED_LABELS) -> None:
        root = f"/repos/{ALLOWED_REPOSITORY}/labels"
        existing = {string(item.get("name")) for item in pages(transport=self.transport, path=root)}
        for name in sorted(names):
            if name not in existing:
                self.transport.write_json(
                    method="POST",
                    path=root,
                    payload={"name": name, "color": "ededed", "description": "Managed by PR lifecycle automation"},
                    mode=Mode.APPLY,
                )

    def collect_reconciliation(self) -> tuple[int, ...]:
        inventory = pages(transport=self.transport, path=f"/repos/{ALLOWED_REPOSITORY}/pulls?state=open")
        preflight(transport=BudgetedReads(transport=self.transport, budget=DEFAULT_BUDGET), human_count=len(inventory))
        changed_count = 0
        entries = {entry.number: entry for entry in self.ledger.entries}
        for item in inventory:
            number = integer(item.get("number"))
            value = collect_snapshot(transport=self.transport, number=number, now=self.clock())
            self.snapshots[number] = value
            entry = observe_activity(
                snapshot=value, previous=reconcile_pending(snapshot=value, previous=entries.get(number))
            )
            entries[number] = entry
            exemptions = closure_exemptions(snapshot=value)
            expected = {
                label
                for label, present in (
                    ("lifecycle-approved", "approval" in exemptions),
                    ("lifecycle-bot", "bot" in exemptions),
                    ("lifecycle-warning", entry.warning is not None),
                )
                if present
            }
            needs_warning_recovery = bool(entry.warning and (exemptions or not entry.warning.final_operation))
            if any(
                (
                    entry.pending,
                    entry.neutralize,
                    warning_needed(snapshot=value, entry=entry, now=self.clock()),
                    expected != set(value.labels) & OWNED_LABELS,
                    any(label.startswith("lifecycle-close-") for label in value.labels),
                    needs_warning_recovery,
                    next_notice(snapshot=value, entry=entry, now=self.clock()) is not None,
                )
            ):
                changed_count += 1
        resources = object_value(object_value(self.transport.get_json(path="/rate_limit")).get("resources"))
        required = changed_count * 120 + QUOTA_RESERVE
        if (
            integer(object_value(resources.get("core")).get("remaining")) < required
            or integer(object_value(resources.get("graphql")).get("remaining")) < changed_count * 12 + QUOTA_RESERVE
        ):
            raise IncompleteDataError("Insufficient quota for planned mutations and cleanup")
        if isinstance(self.transport, GitHubClient) and self.transport.budget - self.transport.requests < required:
            raise IncompleteDataError("Insufficient request budget for planned mutations and cleanup")
        self.ledger = replace(self.ledger, entries=tuple(entries.values()))
        self.persist()
        self.ensure_labels()
        return tuple(integer(item.get("number")) for item in inventory)

    def reconcile(self) -> None:
        for number in self.collect_reconciliation():
            self.reconcile_one(number)

    def reconcile_one(self, number: int) -> None:  # noqa: PLR0915 - Cancellation and delivery share one per-scan notice slot.
        value, entry = self.snapshots[number], self.entry(number)
        if entry is None:
            raise IncompleteDataError("Missing collected state")
        if entry.pending:
            value, entry = self.refresh(number)
        exemptions = closure_exemptions(snapshot=value)
        if entry.warning and exemptions:
            entry = replace(entry, neutralize=entry.warning.cycle, warning=None)
            self.persist(entry=entry)
        if entry.warning and not entry.warning.final_operation:
            entry = replace(entry, neutralize=entry.warning.cycle, warning=None)
            self.persist(entry=entry)
        notice_sent = False
        if entry.neutralize:
            self.comment(number=number, operation=f"cancel:{entry.neutralize}", kind="cancel", cycle=entry.neutralize)
            latest = self.entry(number)
            if latest is None:
                raise IncompleteDataError("Missing cancellation state")
            self.persist(entry=replace(latest, neutralize=None))
            notice_sent = True
        value = self.snapshots[number]
        entry = self.entry(number)
        if entry is None:
            raise IncompleteDataError("Missing reconciled PR state")
        if not notice_sent and warning_needed(snapshot=value, entry=entry, now=self.clock()):
            cycle = digest({"number": number, "activity": entry.activity_at, "now": self.clock().isoformat()})[:24]
            initial = self.comment(number=number, operation=f"warning:{cycle}", kind="warning", cycle=cycle)
            latest = self.entry(number)
            if latest is None:
                raise IncompleteDataError("Missing warning state")
            warning = WarningCycle(
                cycle=cycle,
                delivered_at=initial.at,
                deadline=(timestamp(initial.at) + timedelta(days=14)).isoformat(),
                initial_operation=initial.operation,
            )
            self.persist(entry=replace(latest, warning=warning))
            final = self.comment(
                number=number,
                operation=f"deadline:{cycle}",
                kind="deadline",
                cycle=cycle,
                deadline=warning.deadline,
                identity=initial.identity,
            )
            latest = self.entry(number)
            if latest is None or latest.warning is None:
                raise IncompleteDataError("Activity canceled warning while finalizing deadline")
            self.persist(entry=replace(latest, warning=replace(warning, final_operation=final.operation)))
            notice_sent = True
        value = self.snapshots[number]
        entry = self.entry(number)
        if entry is None:
            raise IncompleteDataError("Missing reconciled warning state")
        if not notice_sent and (kind := next_notice(snapshot=value, entry=entry, now=self.clock())) in {
            "ordinary",
            "milestone-7",
            "milestone-1",
        }:
            cycle = entry.warning.cycle if entry.warning else ""
            operation = (
                f"{kind}:{cycle}"
                if cycle
                else f"ordinary:{digest({'activity': entry.activity_at, 'previous': entry.last_notice_at})[:24]}"
            )
            self.comment(
                number=number,
                operation=operation,
                kind=kind,
                cycle=cycle,
                deadline=entry.warning.deadline if entry.warning else "",
            )
        exemptions = closure_exemptions(snapshot=value)
        for label, present in (
            ("lifecycle-approved", "approval" in exemptions),
            ("lifecycle-bot", "bot" in exemptions),
            ("lifecycle-warning", entry.warning is not None),
        ):
            if (label in value.labels) != present:
                self.label(number=number, label=label, present=present)
        for label in value.labels:
            if owned_label(label) and label.startswith("lifecycle-close-"):
                self.label(number=number, label=label, present=False)
        self.ledger = prune_ledger(
            ledger=self.ledger,
            confirmed_closed=frozenset(),
            gates_cleaned=frozenset(),
            snapshots=tuple(self.snapshots.values()),
        )
        self.persist()

    def prepare(self) -> tuple[int, ...]:
        candidates = []
        for previous in self.ledger.entries:
            if previous.warning is None:
                continue
            value, entry = self.refresh(previous.number)
            if closure_due(snapshot=value, entry=entry, now=self.clock()):
                candidates.append(previous.number)
        preflight(
            transport=BudgetedReads(transport=self.transport, budget=DEFAULT_BUDGET), human_count=len(candidates) * 3
        )
        if candidates:
            self.ensure_labels(names=frozenset({self.gate}))
        for number in candidates:
            self.label(number=number, label=self.gate, present=True)
        verified = []
        for number in candidates:
            value, entry = self.refresh(number)
            if closure_due(snapshot=value, entry=entry, now=self.clock()) and self.gate in value.labels:
                verified.append(number)
            else:
                self.label(number=number, label=self.gate, present=False)
        return tuple(verified)

    def finalize(self) -> tuple[int, ...]:
        errors = []
        for entry in self.ledger.entries:
            try:
                value, _ = self.refresh(entry.number)
                for label in value.labels:
                    if owned_label(label) and label.startswith("lifecycle-close-"):
                        self.label(number=entry.number, label=label, present=False)
            except IncompleteDataError as exc:
                errors.append(f"PR {entry.number}: {exc}")
        if errors:
            raise IncompleteDataError("Gate cleanup failed: " + "; ".join(errors))
        root = f"/repos/{ALLOWED_REPOSITORY}"
        for label in pages(transport=self.transport, path=f"{root}/labels"):
            name = string(label.get("name"))
            if not name.startswith("lifecycle-close-") or not owned_label(name):
                continue
            query = urllib.parse.urlencode({"state": "open", "labels": name})
            if not pages(transport=self.transport, path=f"{root}/issues?{query}"):
                self.transport.write_json(method="DELETE", path=f"{root}/labels/{name}", payload={}, mode=Mode.APPLY)
        closed = frozenset(number for number, value in self.snapshots.items() if value.state == "closed")
        self.ledger = prune_ledger(
            ledger=self.ledger, confirmed_closed=closed, gates_cleaned=closed, snapshots=tuple(self.snapshots.values())
        )
        self.persist()
        return tuple(sorted(closed))

    def refresh_dashboard(self) -> None:
        report = observe(
            repository=ALLOWED_REPOSITORY, transport=self.transport, clock=self.clock, adopted_issue=self.adopted_issue
        )
        if not report.complete:
            raise IncompleteDataError("Dashboard refresh failed: " + "; ".join(report.errors))
        entries = {entry.number: entry for entry in self.ledger.entries}
        for value in report.inventory:
            entry = observe_activity(
                snapshot=value, previous=reconcile_pending(snapshot=value, previous=entries.get(value.number))
            )
            if any(label.startswith("lifecycle-close-") for label in value.labels):
                raise IncompleteDataError(f"PR {value.number}: closure gate remains")
            if (
                entry.pending
                or entry.neutralize
                or (
                    entry.warning
                    and (closure_exemptions(snapshot=value) or not warning_confirmed(snapshot=value, entry=entry))
                )
            ):
                raise IncompleteDataError(f"PR {value.number}: lifecycle reconciliation still required")
            entries[value.number] = entry
        updated = prune_ledger(
            ledger=replace(self.ledger, entries=tuple(entries.values()), last_successful_refresh=report.observed_at),
            confirmed_closed=frozenset(),
            gates_cleaned=frozenset(),
            snapshots=report.inventory,
        )
        body = render_dashboard(report=report, ledger=updated)
        self.persist(ledger=updated, visible=body.split(DASHBOARD_MARKER, 1)[0].rstrip())


def apply_command(
    *,
    command: str,
    transport: WriteTransport,
    clock: Callable[[], datetime],
    run_id: str,
    attempt: str,
    state_path: Path,
    pass_number: int,
    ref: str,
    adopted_issue: int | None = None,
    refresh_dashboard: bool = False,
) -> dict[str, JsonValue]:
    lifecycle = Lifecycle(transport=transport, clock=clock, run_id=run_id, attempt=attempt, adopted_issue=adopted_issue)
    result: dict[str, JsonValue] = {
        "version": 1,
        "mode": "apply",
        "closure_ready": False,
        "continue_scan": False,
        "gate_label": lifecycle.gate,
        "remaining_candidates": 0,
        "complete": False,
    }
    try:
        lifecycle.load()
        if command == "reconcile":
            lifecycle.reconcile()
        elif command == "prepare-close":
            candidates = lifecycle.prepare()
            cache = read_cache(transport=transport, ref=ref) if candidates else None
            state_path.write_text(
                json.dumps(
                    {
                        "gate": lifecycle.gate,
                        "pass": pass_number,
                        "candidates": candidates,
                        "cache": None if cache is None else asdict(cache),
                    }
                ),
                encoding="utf-8",
            )
            result.update(closure_ready=bool(candidates), remaining_candidates=len(candidates))
        elif command == "verify-close":
            saved = object_value(json.loads(state_path.read_text(encoding="utf-8")))
            if saved.get("gate") != lifecycle.gate or saved.get("pass") != pass_number:
                raise IncompleteDataError("Wrong run or pass verification state")
            candidates = tuple(integer(item) for item in array(saved.get("candidates")))
            remaining = verify_candidates(transport=transport, candidates=candidates)
            raw_cache = saved.get("cache")
            before = None
            if raw_cache is not None:
                value = object_value(raw_cache)
                before = CacheRecord(
                    identity=integer(value.get("identity")),
                    created_at=string(value.get("created_at")),
                    last_accessed_at=string(value.get("last_accessed_at")),
                    size_in_bytes=integer(value.get("size_in_bytes")),
                )
            after = read_cache(transport=transport, ref=ref)
            again = continuation(
                pass_number=pass_number, before=before, after=after, previous=candidates, remaining=remaining
            )
            result.update(
                continue_scan=again,
                remaining_candidates=len(remaining),
                confirmed_closed=[number for number in candidates if number not in remaining],
            )
        elif command == "finalize":
            result["confirmed_closed"] = list(lifecycle.finalize())
            if refresh_dashboard:
                lifecycle.refresh_dashboard()
                result["dashboard_refreshed"] = True
        else:
            raise IncompleteDataError("Unsupported apply command")
        result["last_successful_refresh"] = lifecycle.ledger.last_successful_refresh
        result["complete"] = True
    except (IncompleteDataError, OSError, json.JSONDecodeError) as exc:
        result["error"] = str(exc)
        result["closure_ready"] = False
        result["continue_scan"] = False
    result["confirmed_new_receipts"] = len(lifecycle.confirmed_operations)
    return result


def main(  # noqa: PLR0915 - CLI modes share argument and output validation.
    argv: list[str] | None = None, *, transport: ReadTransport | None = None, clock: Callable[[], datetime] = utc_now
) -> int:
    parser = argparse.ArgumentParser(description="Observe Infrahub pull-request lifecycle state")
    parser.add_argument(
        "command",
        nargs="?",
        choices=("observe", "reconcile", "prepare-close", "verify-close", "finalize"),
        default="observe",
    )
    parser.add_argument("--repository", required=True, choices=(ALLOWED_REPOSITORY,))
    parser.add_argument("--mode", choices=tuple(Mode), default=Mode.OBSERVE)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--dashboard-preview", type=Path)
    parser.add_argument("--adopt-dashboard", type=int)
    parser.add_argument("--refresh-dashboard", action="store_true")
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--attempt", default="")
    parser.add_argument("--state", type=Path)
    parser.add_argument("--pass-number", type=int, choices=range(1, MAX_PASSES + 1), default=1)
    parser.add_argument("--ref", default="refs/heads/stable")
    args = parser.parse_args(args=argv)
    if args.mode == Mode.APPLY:
        if args.command == "observe" or not args.run_id or not args.attempt or args.state is None:
            parser.error("Apply requires a mutation command, run ID, attempt, and state path")
        if transport is None:
            transport = GitHubClient(
                token=os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", ""), budget=args.budget
            )
        if not isinstance(transport, WriteTransport):
            parser.error("Apply requires a write transport")
        result = apply_command(
            command=args.command,
            transport=transport,
            clock=clock,
            run_id=args.run_id,
            attempt=args.attempt,
            state_path=args.state,
            pass_number=args.pass_number,
            ref=args.ref,
            adopted_issue=args.adopt_dashboard,
            refresh_dashboard=args.refresh_dashboard,
        )
        serialized = json.dumps(result, indent=2) + "\n"
        if args.report:
            args.report.write_text(serialized, encoding="utf-8")
        else:
            print(serialized, end="")
        if output := os.environ.get("GITHUB_OUTPUT"):
            with Path(output).open("a", encoding="utf-8") as stream:
                for key in ("closure_ready", "continue_scan", "gate_label", "remaining_candidates"):
                    value = result[key]
                    stream.write(f"{key}={str(value).lower() if isinstance(value, bool) else value}\n")
        if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
            with Path(summary).open("a", encoding="utf-8") as stream:
                stream.write(f"Lifecycle {args.command}: {'complete' if result['complete'] else 'FAILED'}.\n")
                stream.write(
                    f"Verified closed PRs: {result.get('confirmed_closed', [])}; confirmed new receipts: {result.get('confirmed_new_receipts', 0)}.\n"
                )
                stream.write(f"Dashboard refreshed: {result.get('dashboard_refreshed', False)}.\n")
                if result.get("error"):
                    stream.write(dashboard_text(str(result["error"])) + "\n")
        return 0 if result["complete"] else 1
    report = observe(
        repository=args.repository,
        transport=transport,
        clock=clock,
        budget=args.budget,
        adopted_issue=args.adopt_dashboard,
    )
    if args.dashboard_preview and report.dashboard_preview is not None:
        args.dashboard_preview.write_text(report.dashboard_preview, encoding="utf-8")
    serialized = json.dumps(asdict(report), indent=2) + "\n"
    if args.report is not None:
        args.report.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as stream:
            stream.write(
                f"Observation {'complete' if report.complete else 'FAILED'}: "
                f"{report.evaluated_count}/{report.inventory_count} PRs evaluated, "
                f"{len(report.excluded_bots)} excluded bots, {report.requests} reads. Closure disabled.\n"
            )
            stream.writelines(f"- {error}\n" for error in report.errors)
    return 0 if report.complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
