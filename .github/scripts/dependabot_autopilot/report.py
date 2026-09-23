"""The verdict report handed over by the analysis workflow, validated as untrusted input."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

REPORT_FILENAME = "verdict.json"
MAX_REPORT_BYTES = 256 * 1024
MAX_REPORT_MARKDOWN_CHARS = 60_000
MAX_OPPORTUNITY_TITLE_CHARS = 120
SCHEMA_VERSION = 1

_HEAD_SHA = re.compile(r"[0-9a-f]{40}")
_OPPORTUNITY_KEY = re.compile(r"[a-z0-9._-]+:[a-z0-9._/-]+")
_CODE_REF = re.compile(r"[^:]+:[0-9]+")
_HTML_COMMENT = re.compile(r"<!--.*?(?:-->|\Z)", flags=re.DOTALL)
_MENTION = re.compile(r"@(?=[A-Za-z0-9])")

_REPORT_FIELDS = frozenset({"schema_version", "pr_number", "head_sha", "verdict", "packages", "report_markdown"})
_PACKAGE_FIELDS = frozenset({"name", "ecosystem", "from_version", "to_version", "verdict", "impacts", "opportunities"})
_IMPACT_FIELDS = frozenset({"summary", "path", "line"})
_OPPORTUNITY_FIELDS = frozenset({"key", "title", "category", "summary", "code_refs"})


class ReportError(Exception):
    """The verdict report is missing, oversized or does not match the schema."""


class Verdict(StrEnum):
    SAFE_TO_MERGE = "safe-to-merge"
    NEEDS_CODE_CHANGES = "needs-code-changes"
    REVIEW_REQUIRED = "review-required"

    @property
    def strictness(self) -> int:
        """Rank where a higher value overrides a lower one when verdicts are combined."""
        return _VERDICT_STRICTNESS[self]


_VERDICT_STRICTNESS = {
    Verdict.SAFE_TO_MERGE: 0,
    Verdict.REVIEW_REQUIRED: 1,
    Verdict.NEEDS_CODE_CHANGES: 2,
}


class Ecosystem(StrEnum):
    GITHUB_ACTIONS = "github-actions"
    UV = "uv"
    NPM = "npm"


class OpportunityCategory(StrEnum):
    SECURITY = "security"
    DEPRECATION_DEADLINE = "deprecation-deadline"
    PERFORMANCE = "performance"
    SIMPLIFICATION = "simplification"
    OTHER = "other"


@dataclass(frozen=True)
class Impact:
    summary: str
    path: str
    line: int


@dataclass(frozen=True)
class Opportunity:
    key: str
    title: str
    category: OpportunityCategory
    summary: str
    code_refs: tuple[str, ...]
    """`path:line` references."""


@dataclass(frozen=True)
class PackageFinding:
    name: str
    ecosystem: Ecosystem
    from_version: str
    to_version: str
    verdict: Verdict
    impacts: tuple[Impact, ...]
    opportunities: tuple[Opportunity, ...]


@dataclass(frozen=True)
class VerdictReport:
    pr_number: int
    head_sha: str
    verdict: Verdict
    packages: tuple[PackageFinding, ...]
    report_markdown: str


def load_report(*, directory: Path) -> VerdictReport:
    """Read and validate `verdict.json` from an extracted artifact directory.

    Raises:
        ReportError: When the file is missing, a symlink, over 256 KB, not JSON, or off-schema.

    """
    path = directory / REPORT_FILENAME
    if path.is_symlink() or not path.is_file():
        raise ReportError(f"{REPORT_FILENAME} is missing from the artifact or is not a regular file")
    with path.open("rb") as handle:
        raw = handle.read(MAX_REPORT_BYTES + 1)
    if len(raw) > MAX_REPORT_BYTES:
        raise ReportError(f"{REPORT_FILENAME} exceeds the 256 KB limit")
    try:
        content = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReportError(f"{REPORT_FILENAME} is not valid JSON: {exc}") from exc
    return _parse_report(value=content)


def sanitize_report_markdown(*, text: str) -> str:
    """Make agent-written Markdown safe to post: no mentions, no HTML comments, visibly labelled."""
    stripped = text
    while (next_pass := _HTML_COMMENT.sub("", stripped)) != stripped:
        stripped = next_pass
    neutralized = _MENTION.sub("@\u200b", stripped)
    return (
        f"<details>\n<summary>Dependency analysis (agent output, unverified)</summary>\n\n{neutralized}\n\n</details>"
    )


def _parse_report(*, value: object) -> VerdictReport:
    report = _object(value=value, fields=_REPORT_FIELDS, where="report")
    schema_version = _integer(value=report["schema_version"], where="schema_version")
    if schema_version != SCHEMA_VERSION:
        raise ReportError(f"schema_version must be {SCHEMA_VERSION}, got {schema_version}")
    pr_number = _integer(value=report["pr_number"], where="pr_number")
    if pr_number < 1:
        raise ReportError("pr_number must be at least 1")
    head_sha = _string(value=report["head_sha"], where="head_sha")
    if not _HEAD_SHA.fullmatch(head_sha):
        raise ReportError("head_sha must be 40 lowercase hexadecimal characters")
    report_markdown = _string(value=report["report_markdown"], where="report_markdown", non_empty=True)
    if len(report_markdown) > MAX_REPORT_MARKDOWN_CHARS:
        raise ReportError(f"report_markdown exceeds {MAX_REPORT_MARKDOWN_CHARS} characters")
    packages = _array(value=report["packages"], where="packages")
    if not packages:
        raise ReportError("packages must contain at least one entry")
    return VerdictReport(
        pr_number=pr_number,
        head_sha=head_sha,
        verdict=_enum(enum=Verdict, value=report["verdict"], where="verdict"),
        packages=tuple(
            _parse_package(value=package, where=f"packages[{index}]") for index, package in enumerate(packages)
        ),
        report_markdown=report_markdown,
    )


def _parse_package(*, value: object, where: str) -> PackageFinding:
    package = _object(value=value, fields=_PACKAGE_FIELDS, where=where)
    verdict = _enum(enum=Verdict, value=package["verdict"], where=f"{where}.verdict")
    impacts = tuple(
        _parse_impact(value=impact, where=f"{where}.impacts[{index}]")
        for index, impact in enumerate(_array(value=package["impacts"], where=f"{where}.impacts"))
    )
    if verdict is Verdict.NEEDS_CODE_CHANGES and not impacts:
        raise ReportError(f"{where} is needs-code-changes but lists no impacts")
    return PackageFinding(
        name=_string(value=package["name"], where=f"{where}.name", non_empty=True),
        ecosystem=_enum(enum=Ecosystem, value=package["ecosystem"], where=f"{where}.ecosystem"),
        from_version=_string(value=package["from_version"], where=f"{where}.from_version"),
        to_version=_string(value=package["to_version"], where=f"{where}.to_version"),
        verdict=verdict,
        impacts=impacts,
        opportunities=tuple(
            _parse_opportunity(value=opportunity, where=f"{where}.opportunities[{index}]")
            for index, opportunity in enumerate(_array(value=package["opportunities"], where=f"{where}.opportunities"))
        ),
    )


def _parse_impact(*, value: object, where: str) -> Impact:
    impact = _object(value=value, fields=_IMPACT_FIELDS, where=where)
    line = _integer(value=impact["line"], where=f"{where}.line")
    if line < 1:
        raise ReportError(f"{where}.line must be at least 1")
    return Impact(
        summary=_string(value=impact["summary"], where=f"{where}.summary", non_empty=True),
        path=_string(value=impact["path"], where=f"{where}.path", non_empty=True),
        line=line,
    )


def _parse_opportunity(*, value: object, where: str) -> Opportunity:
    opportunity = _object(value=value, fields=_OPPORTUNITY_FIELDS, where=where)
    key = _string(value=opportunity["key"], where=f"{where}.key")
    if not _OPPORTUNITY_KEY.fullmatch(key):
        raise ReportError(f"{where}.key must look like '<package>:<identifier>' in lowercase")
    title = _string(value=opportunity["title"], where=f"{where}.title", non_empty=True)
    if len(title) > MAX_OPPORTUNITY_TITLE_CHARS:
        raise ReportError(f"{where}.title exceeds {MAX_OPPORTUNITY_TITLE_CHARS} characters")
    code_refs = tuple(
        _string(value=code_ref, where=f"{where}.code_refs[{index}]")
        for index, code_ref in enumerate(_array(value=opportunity["code_refs"], where=f"{where}.code_refs"))
    )
    for code_ref in code_refs:
        if not _CODE_REF.fullmatch(code_ref):
            raise ReportError(f"{where}.code_refs entry {code_ref!r} is not 'path:line'")
    return Opportunity(
        key=key,
        title=title,
        category=_enum(enum=OpportunityCategory, value=opportunity["category"], where=f"{where}.category"),
        summary=_string(value=opportunity["summary"], where=f"{where}.summary", non_empty=True),
        code_refs=code_refs,
    )


def _object(*, value: object, fields: frozenset[str], where: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ReportError(f"{where} must be an object")
    keys = {str(key) for key in value}
    if missing := fields - keys:
        raise ReportError(f"{where} is missing {sorted(missing)}")
    if unknown := keys - fields:
        raise ReportError(f"{where} has unknown fields {sorted(unknown)}")
    return {str(key): item for key, item in value.items()}


def _array(*, value: object, where: str) -> list[object]:
    if not isinstance(value, list):
        raise ReportError(f"{where} must be an array")
    return list(value)


def _string(*, value: object, where: str, non_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ReportError(f"{where} must be a string")
    if non_empty and not value:
        raise ReportError(f"{where} must not be empty")
    return value


def _integer(*, value: object, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ReportError(f"{where} must be an integer")
    return value


def _enum[E: StrEnum](*, enum: type[E], value: object, where: str) -> E:
    text = _string(value=value, where=where)
    try:
        return enum(text)
    except ValueError as exc:
        raise ReportError(f"{where} has unknown value {text!r}") from exc
