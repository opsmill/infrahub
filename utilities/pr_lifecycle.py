from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

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
MAX_PASSES = 3
QUOTA_RESERVE = 50
REST_READS_PER_PR = 8
DEFAULT_BUDGET = 5000
type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None


class IncompleteDataError(ValueError):
    pass


class Mode(StrEnum):
    OBSERVE = "observe"


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
        + tuple(string(item.get("state")) for item in statuses),
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
    receipts: tuple[Receipt, ...] = ()
    pending: Intent | None = None
    warning: str | None = None
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
    return replace(entry, pending=None, receipts=(*entry.receipts, receipt))


def recover_receipt(*, intent: Intent, feed: tuple[FeedItem, ...]) -> Receipt | None:
    matches = [
        item
        for item in feed
        if item.actor == TRUSTED_BOT and item.kind == intent.kind and item.content_hash == intent.content_hash
    ]
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


def observe_activity(*, snapshot: Snapshot, previous: Entry | None) -> Entry:
    watermarks = tuple(sorted((item.identity, item.content_hash) for item in snapshot.feed))
    if previous is None:
        activity = max([snapshot.updated_at, *(item.at for item in snapshot.feed)])
        return Entry(
            number=snapshot.number,
            node_id=snapshot.node_id,
            activity_at=activity,
            observed_at=snapshot.observed_at,
            raw_updated_at=snapshot.updated_at,
            fingerprint=snapshot.fingerprint,
            head=snapshot.head,
            labels=snapshot.labels,
            watermarks=watermarks,
        )
    if previous.number != snapshot.number or previous.node_id != snapshot.node_id:
        raise IncompleteDataError("Ledger PR identity mismatch")
    known = dict(previous.watermarks)
    changed = [item for item in snapshot.feed if known.get(item.identity) != item.content_hash]
    owned = {
        (receipt.identity, receipt.actor, receipt.kind, receipt.at, receipt.content_hash)
        for receipt in previous.receipts
        if receipt.actor == TRUSTED_BOT
    }
    external = [
        item for item in changed if (item.identity, item.actor, item.kind, item.at, item.content_hash) not in owned
    ]
    reopened = [item for item in external if item.kind == "reopened"]
    activity = previous.activity_at
    changed_head = previous.head != snapshot.head
    unexplained = previous.fingerprint != snapshot.fingerprint or bool(
        set(known) - {item.identity for item in snapshot.feed}
    )
    owned_times = {item.at for item in changed if item not in external}
    if previous.raw_updated_at != snapshot.updated_at and snapshot.updated_at not in owned_times:
        unexplained = True
    if previous.labels != snapshot.labels and not any(item.kind in ("labeled", "unlabeled") for item in changed):
        unexplained = True
    if external:
        activity = max(activity, *(item.at for item in external))
    if changed_head or unexplained:
        activity = max(activity, snapshot.observed_at)
    if reopened:
        activity = max(item.at for item in reopened)
    reset = bool(external) or changed_head or unexplained
    return replace(
        previous,
        activity_at=activity,
        observed_at=snapshot.observed_at,
        raw_updated_at=snapshot.updated_at,
        fingerprint=snapshot.fingerprint,
        head=snapshot.head,
        labels=snapshot.labels,
        watermarks=watermarks,
        warning=None if reset else previous.warning,
        last_notice_at=None if reopened else previous.last_notice_at,
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
            )
        marks = []
        for raw_mark in array(item.get("watermarks")):
            mark = array(raw_mark)
            if len(mark) != WATERMARK_FIELDS:
                raise IncompleteDataError("Invalid feed watermark")
            marks.append((string(mark[0]), string(mark[1])))
        warning = item.get("warning")
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
                receipts=tuple(receipts),
                pending=pending,
                warning=None if warning is None else string(warning),
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


def prune_ledger(*, ledger: Ledger, confirmed_closed: frozenset[int], gates_cleaned: frozenset[int]) -> Ledger:
    return replace(
        ledger,
        entries=tuple(
            entry
            for entry in ledger.entries
            if entry.number not in confirmed_closed & gates_cleaned or entry.pending is not None
        ),
    )


def discover_dashboard(*, transport: ReadTransport) -> tuple[int, str] | None:
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
        raise IncompleteDataError(f"Three-pass bound exhausted; deferred PRs: {remaining}")
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


def guard_repository(repository: str) -> None:
    if repository != ALLOWED_REPOSITORY:
        raise ValueError(f"Repository must be {ALLOWED_REPOSITORY}")


def observe(
    *,
    repository: str,
    transport: ReadTransport | None,
    clock: Callable[[], datetime] = utc_now,
    budget: int = DEFAULT_BUDGET,
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
    try:
        dashboard = discover_dashboard(transport=reads)
        if dashboard:
            decode_ledger(body=dashboard[1])
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
            elif kind == "User":
                humans.append(number)
            else:
                raise IncompleteDataError("Unknown PR author type")
        preflight(transport=reads, human_count=len(humans))
        snapshots.extend(collect_snapshot(transport=reads, number=number, now=now) for number in humans)
    except IncompleteDataError as exc:
        errors.append(str(exc))
    return ObservationReport(
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
    )


def main(
    argv: list[str] | None = None, *, transport: ReadTransport | None = None, clock: Callable[[], datetime] = utc_now
) -> int:
    parser = argparse.ArgumentParser(description="Observe Infrahub pull-request lifecycle state")
    parser.add_argument("command", nargs="?", choices=("observe",), default="observe")
    parser.add_argument("--repository", required=True, choices=(ALLOWED_REPOSITORY,))
    parser.add_argument("--mode", choices=(Mode.OBSERVE,), default=Mode.OBSERVE)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    args = parser.parse_args(args=argv)
    report = observe(repository=args.repository, transport=transport, clock=clock, budget=args.budget)
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
