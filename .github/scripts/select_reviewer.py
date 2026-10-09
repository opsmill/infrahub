#!/usr/bin/env python3
"""Pick one individual reviewer for a pull request and write the decision as JSON.

The first override in the config matching the pull request's author or changed files decides,
whatever the reviewer's load. Otherwise listed reviewers are scored on the changed files by
recency-weighted commits over the last year plus reviews of earlier merged pull requests touching
them, and the best one who is not the author, not away and under the load cap wins. When nobody has
history on the files, the first matching fallback list is used, least loaded first. The next two
eligible people are reported as backups.

Only stdlib, `git` and the `gh` CLI. Every GitHub input can instead be passed as a JSON file, for
dry runs and replays.

Usage:
  select_reviewer.py --github OWNER/NAME --pr N [--out FILE] [--summary FILE] [--github-output FILE]
  select_reviewer.py --pr-json PR.json --reviews-json REVIEWS.json [--logins-json LOGINS.json]
                     [--loads-json LOADS.json] [--at ISO-TIME]
  select_reviewer.py --check
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import math
import re
import shutil
import subprocess  # noqa: S404
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

DAY = 86400
HISTORY_DAYS = 365
HALF_LIFE_DAYS = 180
BULK_FILES = 50
REVIEW_PRS = 200
SCORED = 8
BACKUPS = 2
DEFAULT_CONFIG = Path("dev/REVIEWERS.yml")
BOT = re.compile(r"\[bot\]|dependabot|github-actions|renovate|noreply@anthropic\.com", re.IGNORECASE)
NOREPLY = re.compile(r"^(?:\d+\+)?([^@]+)@users\.noreply\.github\.com$", re.IGNORECASE)

MERGED_PRS_QUERY = """
query($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(states: MERGED, first: 25, after: $after, orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        mergedAt
        author { login }
        files(first: 100) { nodes { path } }
        reviews(first: 50) { nodes { author { __typename login } } }
      }
    }
  }
}
"""

JsonDict = dict[str, Any]


@dataclass
class Inputs:
    """Everything the decision reads besides the config."""

    repo: Path
    pr: JsonDict
    reviews: list[JsonDict]
    logins: dict[str, str]
    loads: dict[str, int]
    at: int


@dataclass
class Candidate:
    login: str
    source: str
    enforced: bool = False
    load: int | None = None
    skip: str | None = None

    def as_dict(self) -> JsonDict:
        return {"login": self.login, "source": self.source, "load": self.load, "skip": self.skip}


# --- helpers ---------------------------------------------------------------------------------


def glob_match(path: str, pattern: str) -> bool:
    """`**` spans any number of folders (also none), `*` stays within one path segment."""
    rx, i = "", 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            rx, i = rx + "(?:.*/)?", i + 3
        elif pattern.startswith("**", i):
            rx, i = rx + ".*", i + 2
        elif pattern[i] == "*":
            rx, i = rx + "[^/]*", i + 1
        else:
            rx, i = rx + re.escape(pattern[i]), i + 1
    return re.fullmatch(rx, path) is not None


def matches_any(paths: list[str], patterns: list[str]) -> bool:
    return any(glob_match(p, g) for p in paths for g in patterns)


def iso_ts(iso: str) -> int:
    return int(datetime.fromisoformat(iso).timestamp())


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout  # noqa: S603, S607


def gh(*args: str, attempts: int = 4) -> object:
    """Parsed JSON output of `gh`, retried because GitHub's GraphQL API times out on heavy pages.

    Raises:
        RuntimeError: `gh` still fails after the last attempt.

    """
    stderr = ""
    for attempt in range(attempts):
        proc = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)  # noqa: S603, S607
        if proc.returncode == 0:
            return json.loads(proc.stdout) if proc.stdout.strip() else None
        stderr = proc.stderr.strip()
        if attempt < attempts - 1:
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError(f"gh {' '.join(args[:2])} failed: {stderr[:300]}")


def gh_dict(*args: str) -> JsonDict:
    """Like `gh`, for calls that return a JSON object.

    Raises:
        RuntimeError: the output is not a JSON object.

    """
    data = gh(*args)
    if not isinstance(data, dict):
        raise RuntimeError(f"gh {' '.join(args[:2])}: expected a JSON object")
    return {str(k): v for k, v in data.items()}


def gh_pages(path: str) -> list[Any]:
    """Every item of a paginated REST list, flattened from `--slurp`'s list of pages."""
    pages = gh("api", f"{path}?per_page=100", "--paginate", "--slurp")
    return [item for page in pages if isinstance(page, list) for item in page] if isinstance(pages, list) else []


def warn(message: str) -> None:
    """A GitHub Actions warning annotation, also readable in a terminal."""
    print(f"::warning::{message}", file=sys.stderr)


def read_json(path: Path) -> Any:  # noqa: ANN401
    return json.loads(path.read_text(encoding="utf-8"))


def load_config(path: Path) -> JsonDict:
    """REVIEWERS.yml parsed with PyYAML or `yq` (preinstalled on GitHub runners), or a JSON copy."""
    if path.suffix == ".json":
        data = read_json(path)
    elif importlib.util.find_spec("yaml"):
        data = importlib.import_module("yaml").safe_load(path.read_text(encoding="utf-8"))
    elif yq := shutil.which("yq"):
        data = json.loads(subprocess.run([yq, "-o=json", str(path)], capture_output=True, text=True, check=True).stdout)  # noqa: S603
    else:
        sys.exit("reading REVIEWERS.yml needs PyYAML or `yq`, or pass a JSON copy of it with --config")
    if not isinstance(data, dict):
        sys.exit(f"{path}: expected a mapping at the top level")
    return data


def pool(config: JsonDict) -> dict[str, str]:
    """Logins the score and fallback may pick, lower-cased to as written."""
    return {x.lower(): x for x in config.get("reviewers") or []}


def people(config: JsonDict) -> list[str]:
    """Every login the config can return."""
    named = set(pool(config).values())
    for o in config.get("overrides") or []:
        named |= set(o.get("reviewers") or [])
    return sorted(named)


# --- GitHub inputs ---------------------------------------------------------------------------


def fetch_pr(github: str, number: int) -> JsonDict:
    pr = gh_dict("api", f"repos/{github}/pulls/{number}")
    base = f"repos/{github}/pulls/{number}"
    return {
        "number": number,
        "author": pr["user"]["login"],
        "author_is_bot": pr["user"]["type"] == "Bot",
        "draft": bool(pr["draft"]),
        "head_repo": (pr["head"].get("repo") or {}).get("full_name", ""),
        "base": pr["base"]["ref"],
        "created_at": pr["created_at"],
        "requested_users": [u["login"] for u in pr.get("requested_reviewers") or [] if u["type"] == "User"],
        "reviewed_by": sorted({r["user"]["login"] for r in gh_pages(f"{base}/reviews") if r["user"]["type"] == "User"}),
        "files": [{"path": f["filename"], "lines": f["additions"] + f["deletions"]} for f in gh_pages(f"{base}/files")],
        "commits": [c["sha"] for c in gh_pages(f"{base}/commits")],
    }


def human_reviewers(pr: JsonDict) -> list[str]:
    author = (pr.get("author") or {}).get("login", "")
    return sorted(
        {
            r["author"]["login"]
            for r in pr["reviews"]["nodes"]
            if r.get("author") and r["author"].get("__typename") == "User" and r["author"]["login"] != author
        }
    )


def fetch_reviews(github: str, limit: int = REVIEW_PRS) -> list[JsonDict]:
    owner, name = github.split("/")
    out: list[JsonDict] = []
    after: str | None = None
    while len(out) < limit:
        args = ["api", "graphql", "-f", f"query={MERGED_PRS_QUERY}", "-f", f"owner={owner}", "-f", f"name={name}"]
        if after:
            args += ["-f", f"after={after}"]
        page = gh_dict(*args)["data"]["repository"]["pullRequests"]
        out.extend(
            {
                "merged_at": pr["mergedAt"],
                "files": [f["path"] for f in pr["files"]["nodes"]],
                "reviewers": human_reviewers(pr),
            }
            for pr in page["nodes"]
        )
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    return out[:limit]


def fetch_logins(github: str, logins: list[str]) -> dict[str, str]:
    """Commit email to login, for the config's people only (the search API allows 30 calls a minute)."""
    out: dict[str, str] = {}
    for login in logins:
        query = f"search/commits?q=repo:{github}+author:{login}&per_page=100"
        try:
            data = gh("api", query, "--jq", "[.items[].commit.author.email] | unique")
        except RuntimeError as exc:
            # A burst of pull requests can exhaust the search quota; noreply emails still resolve.
            warn(f"commit emails of {login} unknown: {exc}")
            continue
        out |= {str(e).lower(): login for e in data} if isinstance(data, list) else {}
    return out


def fetch_loads(github: str, logins: list[str]) -> dict[str, int]:
    """Open pull requests requesting each login directly; team requests from CODEOWNERS don't count."""
    loads: dict[str, int] = {}
    for login in logins:
        search = ["--state", "open", "--search", f"user-review-requested:{login}", "--json", "number"]
        try:
            found = gh("pr", "list", "-R", github, *search)
        except RuntimeError as exc:
            warn(f"load of {login} unknown, so not capped: {exc}")
            continue
        loads[login] = len(found) if isinstance(found, list) else 0
    return loads


# --- gate ------------------------------------------------------------------------------------


def gate(config: JsonDict, pr: JsonDict, github: str | None) -> str | None:
    """Why no reviewer should be requested at all, or None to go ahead."""
    if github and pr.get("head_repo", github) != github:
        return "pull request from another repository"
    if pr.get("draft"):
        return "draft pull request"
    if pr.get("author_is_bot") and pr["author"] not in (config.get("bot_authors") or []):
        return "opened by a bot"
    reviewed = {x.lower() for x in pr.get("reviewed_by") or []} - {pr["author"].lower()}
    if pr.get("requested_users") or reviewed:
        return "already has an individual reviewer"
    return None


# --- score -----------------------------------------------------------------------------------


def decay(ts: int, at: int) -> float:
    return math.pow(0.5, (at - ts) / (HALF_LIFE_DAYS * DAY))


def shares(scores: dict[str, float]) -> dict[str, float]:
    total = sum(scores.values())
    return {k: v / total for k, v in scores.items()} if total else {}


def commit_sizes(inputs: Inputs, since: int) -> dict[str, int]:
    """Files touched by each commit in the window, so bulk commits can be skipped."""
    log = git(
        inputs.repo,
        "log",
        "--no-merges",
        "--no-renames",
        f"--since=@{since}",
        f"--until=@{inputs.at}",
        "--format=\x1e%H",
        "--name-only",
    )
    sizes: dict[str, int] = {}
    for record in log.split("\x1e")[1:]:
        sha, *files = record.strip().splitlines()
        sizes[sha] = sum(1 for f in files if f)
    return sizes


def code_scores(inputs: Inputs, scope: list[str], since: int) -> dict[str, float]:
    window = [f"--since=@{since}", f"--until=@{inputs.at}"]
    # Without --no-renames, rename detection would download file contents in a blobless clone.
    log = git(
        inputs.repo, "log", "--no-merges", "--no-renames", *window, "--format=\x1e%H\x1f%at\x1f%ae\x1f%an", "--", *scope
    )
    sizes = commit_sizes(inputs, since)
    skip = set(inputs.pr["commits"])
    scores: dict[str, float] = defaultdict(float)
    for record in log.split("\x1e")[1:]:
        sha, ts, email, name = record.strip().split("\x1f")
        if sha in skip or BOT.search(f"{name} {email}") or sizes.get(sha, 0) > BULK_FILES:
            continue
        login = inputs.logins.get(email.lower()) or (m.group(1) if (m := NOREPLY.match(email)) else None)
        if login:
            scores[login.lower()] += decay(int(ts), inputs.at)
    return scores


def review_scores(inputs: Inputs, scope: list[str], since: int) -> dict[str, float]:
    prefixes = tuple(s + "/" for s in scope)
    scores: dict[str, float] = defaultdict(float)
    for pr in inputs.reviews:
        merged = iso_ts(pr["merged_at"])
        if since <= merged < inputs.at and any(f in scope or f.startswith(prefixes) for f in pr["files"]):
            for reviewer in pr["reviewers"]:
                if not BOT.search(reviewer):
                    scores[reviewer.lower()] += decay(merged, inputs.at)
    return scores


def existing_files(inputs: Inputs) -> set[str]:
    """Files of the base branch, so a file the pull request adds is new; the checkout without a base."""
    base = inputs.pr.get("base")
    if base:
        try:
            return set(git(inputs.repo, "ls-tree", "-r", "--name-only", f"origin/{base}").splitlines())
        except subprocess.CalledProcessError:
            pass
    return set(git(inputs.repo, "ls-files").splitlines())


def rank(inputs: Inputs, files: list[str], review_weight: float) -> list[tuple[str, float]]:
    """People by recent commits plus reviews on `files`; a new file counts through its folder."""
    known = existing_files(inputs)
    scope = sorted({f if f in known else str(PurePosixPath(f).parent) for f in files} - {"."})
    if not scope:
        return []
    since = inputs.at - HISTORY_DAYS * DAY
    code = shares(code_scores(inputs, scope, since))
    review = shares(review_scores(inputs, scope, since))
    combined = {
        k: (1 - review_weight) * code.get(k, 0) + review_weight * review.get(k, 0) for k in set(code) | set(review)
    }
    return sorted(combined.items(), key=lambda kv: (-kv[1], kv[0]))


# --- decision --------------------------------------------------------------------------------


def changed_paths(config: JsonDict, pr: JsonDict) -> list[str]:
    ignore = config.get("ignore") or []
    return [f["path"] for f in pr["files"] if not any(glob_match(f["path"], g) for g in ignore)]


def matching_override(config: JsonDict, author: str, paths: list[str]) -> JsonDict | None:
    for o in config.get("overrides") or []:
        if o.get("author") and o["author"].lower() != author:
            continue
        if o.get("paths") and not matches_any(paths, o["paths"]):
            continue
        return o
    return None


def fallback_order(config: JsonDict, paths: list[str], number: int, loads: dict[str, int]) -> list[str]:
    """The first matching fallback list, least loaded first, rotated by PR number to spread ties."""
    for fb in config.get("fallback") or []:
        if matches_any(paths, fb.get("paths") or []):
            members = list(fb.get("reviewers") or [])
            if not members:
                return []
            shift = number % len(members)
            return sorted(members[shift:] + members[:shift], key=lambda x: loads.get(x, 0))
    return []


def skip_reason(c: Candidate, config: JsonDict, author: str) -> str | None:
    key = c.login.lower()
    if key == author:
        return "author"
    if key in {a.lower() for a in config.get("away") or []}:
        return "away"
    if c.enforced:
        return None
    if key not in pool(config):
        return "not a listed reviewer"
    cap = config.get("load_cap")
    if cap is not None and c.load is not None and c.load >= cap:
        return f"load {c.load} >= cap {cap}"
    return None


def decide(config: JsonDict, inputs: Inputs) -> JsonDict:
    author = inputs.pr["author"].lower()
    paths = changed_paths(config, inputs.pr)
    if not paths:
        return {"decision": None, "reason": "only ignored files", "backups": [], "chain": []}

    chain: list[Candidate] = []
    if override := matching_override(config, author, paths):
        chain += [Candidate(x, f"override: {override['name']}", enforced=True) for x in override.get("reviewers") or []]
    weight = float(config.get("review_weight", 0.5))
    chain += [Candidate(x, f"score {share:.0%}") for x, share in rank(inputs, paths, weight)[:SCORED]]
    chain += [Candidate(x, "fallback") for x in fallback_order(config, paths, inputs.pr["number"], inputs.loads)]

    seen: set[str] = set()
    annotated: list[Candidate] = []
    for c in chain:
        if c.login.lower() in seen:
            continue
        seen.add(c.login.lower())
        c.login = pool(config).get(c.login.lower(), c.login)
        c.load = inputs.loads.get(c.login)
        c.skip = skip_reason(c, config, author)
        annotated.append(c)

    eligible = [c for c in annotated if c.skip is None]
    capped = sorted((c for c in annotated if (c.skip or "").startswith("load")), key=lambda c: c.load or 0)
    chosen = eligible[0] if eligible else capped[0] if capped else None
    if chosen and chosen.skip:
        chosen.source += ", least loaded (everyone at the cap)"
    backups = [c.login for c in [*eligible, *capped] if c is not chosen and not c.enforced][:BACKUPS]
    return {
        "decision": chosen.as_dict() if chosen else None,
        "reason": None if chosen else "nobody eligible",
        "backups": backups,
        "chain": [c.as_dict() for c in annotated],
    }


def summary(result: JsonDict, number: int) -> str:
    rows = [f"### Reviewer for #{number}"]
    decision = result.get("decision")
    if decision:
        rows.append(f"Requested: `{decision['login']}` ({decision['source']})")
        if result.get("backups"):
            rows.append("Backups: " + ", ".join(f"`{x}`" for x in result["backups"]))
    else:
        rows.append(f"Nobody requested: {result['reason']}")
    skipped = [f"`{c['login']}` ({c['skip']})" for c in result.get("chain", []) if c["skip"]]
    if skipped:
        rows.append("Skipped: " + ", ".join(skipped[:8]))
    return "\n\n".join(rows) + "\n"


# --- config checks ---------------------------------------------------------------------------


def check(config: JsonDict, repo: Path) -> list[str]:
    tracked = git(repo, "ls-files").splitlines()
    listed = set(pool(config).values())
    problems: list[str] = []
    if not listed:
        problems.append("reviewers: the list is empty")
    for o in config.get("overrides") or []:
        label = f"override {o.get('name', '?')!r}"
        problems += [f"{label}: missing {k}" for k in ("name", "reason", "reviewers") if not o.get(k)]
        if not o.get("author") and not o.get("paths"):
            problems.append(f"{label}: needs an author, paths or both")
        problems += [
            f"{label}: pattern matches no file: {p}"
            for p in o.get("paths") or []
            if not any(glob_match(f, p) for f in tracked)
        ]
    for fb in config.get("fallback") or []:
        problems += [f"fallback: {x} is not in reviewers" for x in fb.get("reviewers") or [] if x not in listed]
        problems += [
            f"fallback: pattern matches no file: {p}"
            for p in fb.get("paths") or []
            if not any(glob_match(f, p) for f in tracked)
        ]
    cap = config.get("load_cap")
    if cap is not None and (not isinstance(cap, int) or cap < 1):
        problems.append("load_cap: expected a positive integer")
    weight = config.get("review_weight", 0.5)
    if not isinstance(weight, (int, float)) or not 0 <= weight <= 1:
        problems.append("review_weight: expected a number between 0 and 1")
    return problems


# --- entry point -----------------------------------------------------------------------------


def build_inputs(a: argparse.Namespace, pr: JsonDict, named: list[str]) -> Inputs:
    github: str | None = a.github
    logins = {str(k).lower(): str(v) for k, v in read_json(a.logins_json).items()} if a.logins_json else {}
    if not a.logins_json and github:
        logins = fetch_logins(github, named)
    reviews = read_json(a.reviews_json) if a.reviews_json else fetch_reviews(github) if github else []
    loads = read_json(a.loads_json) if a.loads_json else fetch_loads(github, named) if github else {}
    at = iso_ts(a.at) if a.at else int(time.time())
    return Inputs(repo=a.repo, pr=pr, reviews=reviews, logins=logins, loads=loads, at=at)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--repo", type=Path, default=Path(), help="git checkout with full history")
    p.add_argument("--github", help="OWNER/NAME: fetch every GitHub input with `gh`")
    p.add_argument("--pr", type=int)
    p.add_argument("--pr-json", type=Path)
    p.add_argument("--reviews-json", type=Path)
    p.add_argument("--logins-json", type=Path)
    p.add_argument("--loads-json", type=Path)
    p.add_argument("--at", help="ISO time to decide at (default now; the pull request's creation time for replays)")
    p.add_argument("--out", type=Path, help="write the JSON result here instead of stdout")
    p.add_argument("--summary", type=Path, help="append a Markdown summary here, such as $GITHUB_STEP_SUMMARY")
    p.add_argument("--github-output", type=Path, help="append `login=<login>` here, such as $GITHUB_OUTPUT")
    p.add_argument("--check", action="store_true", help="validate the config and exit")
    a = p.parse_args(argv)
    config = load_config(a.config)

    if a.check:
        problems = check(config, a.repo)
        print("\n".join(problems) or f"{a.config} OK")
        return 1 if problems else 0

    if a.pr_json:
        pr = read_json(a.pr_json)
    elif a.github and a.pr:
        pr = fetch_pr(a.github, a.pr)
    else:
        sys.exit("pass --pr-json, or --github with --pr")

    if skip := gate(config, pr, a.github):
        result: JsonDict = {"decision": None, "reason": skip, "backups": [], "chain": []}
    else:
        result = decide(config, build_inputs(a, pr, people(config)))

    text = json.dumps(result, indent=1)
    if a.out:
        a.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    if a.summary:
        with a.summary.open("a", encoding="utf-8") as fh:
            fh.write(summary(result, pr["number"]))
    if a.github_output:
        with a.github_output.open("a", encoding="utf-8") as fh:
            fh.write(f"login={(result['decision'] or {}).get('login', '')}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
