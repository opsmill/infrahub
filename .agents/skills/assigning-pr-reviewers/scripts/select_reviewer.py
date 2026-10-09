#!/usr/bin/env python3
"""Run levels 1 and 2 of the reviewer cascade for one pull request and write the result as JSON.

Level 1, hardcoded rule: the REVIEWERS.yml subject owning most of the pull request's changed
lines gives its author rules, then its ordered reviewers (`team:<name>` expands to the team,
least loaded first). Level 2, fallback: the people who worked on the dominant files over the
last year (recency-weighted commits) plus who reviewed earlier pull requests on them, then the
team of the first `fallback` scope matching those files.

A candidate is eligible when it is not the author, not in `away`, listed in REVIEWERS.yml (the
workflow allowlist holds the same logins) and under `load_cap` open individual review requests.
If every candidate is capped, the least loaded one wins. Subjects with `concern: true` stay out
of the default decision and are reported separately, for the agent to judge from the diff.

Only stdlib, `git` and the `gh` CLI. Every GitHub input can instead be passed as a JSON file,
for dry runs and replays.

Usage:
  select_reviewer.py --github OWNER/NAME --pr N [--out FILE] [--summary FILE]
  select_reviewer.py --pr-json PR.json --reviews-json REVIEWS.json [--logins-json LOGINS.json]
                     [--loads-json LOADS.json] [--at ISO-TIME]
  select_reviewer.py --check [--workflow .github/workflows/pr-default-reviewer.md]
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import math
import operator
import re
import shutil
import subprocess  # noqa: S404
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

DAY = 86400
HISTORY_DAYS = 365
HALF_LIFE_DAYS = 180
BULK_FILES = 50
REVIEW_PRS = 200
CONTRIBUTORS = 8
BOT = re.compile(r"\[bot\]|dependabot|github-actions|renovate|noreply@anthropic\.com", re.IGNORECASE)
NOREPLY = re.compile(r"^(?:\d+\+)?([^@]+)@users\.noreply\.github\.com$", re.IGNORECASE)
ALLOWLIST = re.compile(r"allowed-reviewers:\n((?:[ \t]+(?:- .*|#.*)\n)+)")

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
    """Everything the cascade reads besides the map."""

    repo: Path
    pr: JsonDict
    reviews: list[JsonDict]
    logins: dict[str, str]
    loads: dict[str, int]
    at: int


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


def gh_list(*args: str) -> list[Any]:
    data = gh(*args)
    return data if isinstance(data, list) else []


def read_json(path: Path) -> Any:  # noqa: ANN401
    return json.loads(path.read_text(encoding="utf-8"))


def load_map(path: Path) -> JsonDict:
    """REVIEWERS.yml parsed with `yq` (preinstalled on GitHub runners) or PyYAML, or a JSON copy."""
    if path.suffix == ".json":
        data = read_json(path)
    elif importlib.util.find_spec("yaml"):
        data = importlib.import_module("yaml").safe_load(path.read_text(encoding="utf-8"))
    elif yq := shutil.which("yq"):
        data = json.loads(subprocess.run([yq, "-o=json", str(path)], capture_output=True, text=True, check=True).stdout)  # noqa: S603
    else:
        sys.exit("reading REVIEWERS.yml needs PyYAML or `yq`, or pass a JSON copy of it with --map")
    if not isinstance(data, dict):
        sys.exit(f"{path}: expected a mapping at the top level")
    return data


def map_logins(m: JsonDict) -> dict[str, str]:
    """Every login the map can return, lower-cased to as written."""
    out: dict[str, str] = {}
    for members in (m.get("teams") or {}).values():
        out |= {x.lower(): x for x in members}
    for s in m.get("subjects") or []:
        out |= {r.lower(): r for r in s.get("reviewers") or [] if not r.startswith("team:")}
        out |= {r["reviewer"].lower(): r["reviewer"] for r in s.get("rules") or []}
    return out


def expand(entry: str, m: JsonDict, loads: dict[str, int]) -> list[str]:
    """A login, or a team's members from least to most loaded, list order breaking ties."""
    if not entry.startswith("team:"):
        return [entry]
    members: list[str] = list((m.get("teams") or {}).get(entry.removeprefix("team:"), []))
    return sorted(members, key=lambda x: (loads.get(x, 0), members.index(x)))


# --- GitHub inputs ---------------------------------------------------------------------------


def fetch_pr(github: str, number: int) -> JsonDict:
    pr = gh_dict("api", f"repos/{github}/pulls/{number}")
    files_jq = "[.[] | {path: .filename, lines: (.additions + .deletions)}]"
    return {
        "number": number,
        "author": pr["user"]["login"],
        "base": pr["base"]["ref"],
        "created_at": pr["created_at"],
        "files": gh_list("api", f"repos/{github}/pulls/{number}/files", "--paginate", "--jq", files_jq),
        "commits": gh_list("api", f"repos/{github}/pulls/{number}/commits", "--paginate", "--jq", "[.[].sha]"),
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
    """Commit email to login, for the map's people only (the search API allows 30 calls a minute)."""
    out: dict[str, str] = {}
    for login in logins:
        query = f"search/commits?q=repo:{github}+author:{login}&per_page=100"
        emails = gh_list("api", query, "--jq", "[.items[].commit.author.email] | unique")
        out |= {str(e).lower(): login for e in emails}
    return out


def fetch_loads(github: str, logins: list[str]) -> dict[str, int]:
    """Open pull requests requesting each login directly; team requests from CODEOWNERS don't count."""
    loads: dict[str, int] = {}
    for login in logins:
        search = f"user-review-requested:{login}"
        loads[login] = len(
            gh_list("pr", "list", "-R", github, "--state", "open", "--search", search, "--json", "number")
        )
    return loads


# --- level 2 ranking -------------------------------------------------------------------------


def decay(ts: int, at: int) -> float:
    return math.pow(0.5, (at - ts) / (HALF_LIFE_DAYS * DAY))


def shares(scores: dict[str, float]) -> dict[str, float]:
    total = sum(scores.values())
    return {k: v / total for k, v in scores.items()} if total else {}


def code_scores(inputs: Inputs, scope: list[str], since: int) -> dict[str, float]:
    log_format = "--format=\x1e%H\x1f%at\x1f%ae\x1f%an"
    window = [f"--since=@{since}", f"--until=@{inputs.at}"]
    log = git(inputs.repo, "log", "--no-merges", *window, log_format, "--name-only", "--", *scope)
    skip = set(inputs.pr["commits"])
    scores: dict[str, float] = defaultdict(float)
    for record in log.split("\x1e")[1:]:
        sha, ts, email, name = record.split("\n", 1)[0].split("\x1f")
        if sha in skip or BOT.search(f"{name} {email}"):
            continue
        login = inputs.logins.get(email.lower()) or (m.group(1) if (m := NOREPLY.match(email)) else None)
        if not login:
            continue
        touched = git(inputs.repo, "show", "--no-renames", "--name-only", "--format=", sha).split()
        if len(touched) <= BULK_FILES:
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


def existing_files(inputs: Inputs) -> str:
    """Files of the base branch, so a file the pull request adds is new; the checkout without a base."""
    base = inputs.pr.get("base")
    if base:
        try:
            return git(inputs.repo, "ls-tree", "-r", "--name-only", f"origin/{base}")
        except subprocess.CalledProcessError:
            pass
    return git(inputs.repo, "ls-files")


def rank_contributors(inputs: Inputs, files: list[str]) -> list[tuple[str, float]]:
    """People by recent commits plus reviews on `files`; a new file counts through its folder."""
    known = set(existing_files(inputs).splitlines())
    scope = sorted({f if f in known else str(PurePosixPath(f).parent) for f in files} - {"."})
    if not scope:
        return []
    since = inputs.at - HISTORY_DAYS * DAY
    code = shares(code_scores(inputs, scope, since))
    review = shares(review_scores(inputs, scope, since))
    combined = {k: (code.get(k, 0) + review.get(k, 0)) / 2 for k in set(code) | set(review)}
    return sorted(combined.items(), key=lambda kv: (-kv[1], kv[0]))


# --- the cascade -----------------------------------------------------------------------------


def classify(m: JsonDict, files: list[JsonDict]) -> tuple[Counter[str], dict[str, list[str]]]:
    """Changed lines per bucket, a subject name or `unmapped`; the last matching subject wins."""
    lines: Counter[str] = Counter()
    members: dict[str, list[str]] = defaultdict(list)
    for f in files:
        path = f["path"]
        if any(glob_match(path, g) for g in m.get("ignore") or []):
            continue
        bucket = "unmapped"
        for s in m.get("subjects") or []:
            if any(glob_match(path, p) for p in s.get("paths") or []):
                bucket = s["name"]
        lines[bucket] += max(1, int(f.get("lines") or 0))
        members[bucket].append(path)
    return lines, dict(members)


def subject_chain(m: JsonDict, subject: JsonDict, author: str, loads: dict[str, int]) -> list[tuple[str, str]]:
    rules = subject.get("rules") or []
    chain = [(r["reviewer"], f"rule for {author}") for r in rules if r["author"].lower() == author]
    for entry in subject.get("reviewers") or []:
        chain.extend((x, f"subject {subject['name']}") for x in expand(entry, m, loads))
    return chain


def fallback_chain(m: JsonDict, files: list[str], loads: dict[str, int]) -> list[tuple[str, str]]:
    for fb in m.get("fallback") or []:
        if any(glob_match(f, p) for f in files for p in fb.get("paths") or []):
            return [(x, f"team {fb['team']}") for x in expand(f"team:{fb['team']}", m, loads)]
    return []


def skip_reason(key: str, load: int | None, m: JsonDict, author: str) -> str | None:
    cap = m.get("load_cap")
    if key == author:
        return "author"
    if key in {a.lower() for a in m.get("away") or []}:
        return "away"
    if key not in map_logins(m):
        return "not in REVIEWERS.yml"
    if cap is not None and load is not None and load >= cap:
        return f"load {load} >= cap {cap}"
    return None


def pick(
    chain: list[tuple[int, str, str]], m: JsonDict, author: str, loads: dict[str, int]
) -> tuple[JsonDict | None, list[JsonDict]]:
    """Annotate the candidate chain with skip reasons and return the first eligible candidate."""
    allowed = map_logins(m)
    seen: set[str] = set()
    annotated: list[JsonDict] = []
    for level, login, source in chain:
        key = login.lower()
        if key in seen:
            continue
        seen.add(key)
        written = allowed.get(key, login)
        load = loads.get(written)
        skip = skip_reason(key, load, m, author)
        annotated.append({"login": written, "level": level, "source": source, "load": load, "skip": skip})
    eligible = [c for c in annotated if c["skip"] is None]
    if eligible:
        return eligible[0], annotated
    capped = [c for c in annotated if str(c["skip"]).startswith("load")]
    if capped:
        best = min(capped, key=operator.itemgetter("load"))
        return best | {"source": f"{best['source']}, least loaded (everyone at the cap)"}, annotated
    return None, annotated


def concern_results(m: JsonDict, inputs: Inputs, lines: Counter[str], concern: set[str]) -> list[JsonDict]:
    subjects = {s["name"]: s for s in m.get("subjects") or []}
    author = inputs.pr["author"].lower()
    results = []
    for name in sorted(concern & set(lines)):
        chain = [(1, login, src) for login, src in subject_chain(m, subjects[name], author, inputs.loads)]
        decision, annotated = pick(chain, m, author, inputs.loads)
        results.append(
            {
                "subject": name,
                "description": subjects[name].get("description", ""),
                "lines": lines[name],
                "decision": decision,
                "chain": annotated,
            }
        )
    return results


def cascade(m: JsonDict, inputs: Inputs) -> JsonDict:
    author = inputs.pr["author"].lower()
    subjects = {s["name"]: s for s in m.get("subjects") or []}
    concern = {name for name, s in subjects.items() if s.get("concern")}
    lines, members = classify(m, inputs.pr["files"])
    if not lines:
        return {"decision": None, "reason": "only ignored files", "buckets": {}}

    default: Counter[str] = Counter()
    for bucket, n in lines.items():
        default["unmapped" if bucket in concern else bucket] += n
    dominant = default.most_common(1)[0][0]
    files = list(members.get(dominant, []))
    if dominant == "unmapped":
        files += [f for b in concern & set(members) for f in members[b]]

    chain: list[tuple[int, str, str]] = []
    if dominant != "unmapped":
        chain.extend((1, login, src) for login, src in subject_chain(m, subjects[dominant], author, inputs.loads))
    ranked = rank_contributors(inputs, files)[:CONTRIBUTORS]
    chain.extend((2, login, f"contributors {share:.0%}") for login, share in ranked)
    chain.extend((2, login, src) for login, src in fallback_chain(m, files, inputs.loads))
    decision, annotated = pick(chain, m, author, inputs.loads)
    return {
        "decision": decision,
        "reason": None if decision else "no reviewer produced by the cascade",
        "buckets": dict(lines),
        "dominant": dominant,
        "chain": annotated,
        "concerns": concern_results(m, inputs, lines, concern),
    }


def summary(result: JsonDict, number: int) -> str:
    buckets = sorted(result.get("buckets", {}).items(), key=lambda kv: -kv[1])
    decision = result.get("decision")
    selected = (
        f"`{decision['login']}` (level {decision['level']}, {decision['source']})"
        if decision
        else f"none ({result['reason']})"
    )
    rows = [
        f"### Reviewer cascade for #{number}",
        "Changed lines per subject: " + (", ".join(f"{b} {n}" for b, n in buckets) or "none"),
        f"Dominant: `{result.get('dominant', '-')}`",
        f"Selected: {selected}",
    ]
    skipped = [f"`{c['login']}` ({c['skip']})" for c in result.get("chain", []) if c["skip"]]
    if skipped:
        rows.append("Skipped: " + ", ".join(skipped[:8]))
    return "\n".join(rows) + "\n"


# --- map checks ------------------------------------------------------------------------------


def check(m: JsonDict, repo: Path, workflow: Path | None) -> list[str]:
    tracked = git(repo, "ls-files").splitlines()
    teams = m.get("teams") or {}
    subjects = m.get("subjects") or []
    problems = [
        f"subject {s['name']}: pattern matches no file: {p}"
        for s in subjects
        for p in s.get("paths") or []
        if not any(glob_match(f, p) for f in tracked)
    ]
    problems += [
        f"subject {s['name']}: unknown team {e}"
        for s in subjects
        for e in s.get("reviewers") or []
        if e.startswith("team:") and e.removeprefix("team:") not in teams
    ]
    problems += [
        f"fallback: unknown team {fb.get('team')}" for fb in m.get("fallback") or [] if fb.get("team") not in teams
    ]
    if workflow:
        block = ALLOWLIST.search(workflow.read_text(encoding="utf-8"))
        allow = set(re.findall(r"- (\S+)", block.group(1))) if block else set()
        logins = set(map_logins(m).values())
        problems += [
            f"{x} is in REVIEWERS.yml but not in allowed-reviewers of {workflow}" for x in sorted(logins - allow)
        ]
        problems += [
            f"{x} is in allowed-reviewers of {workflow} but not in REVIEWERS.yml" for x in sorted(allow - logins)
        ]
    return problems


def read_logins(path: Path) -> dict[str, str]:
    return {str(k).lower(): str(v) for k, v in read_json(path).items()}


def build_inputs(a: argparse.Namespace, people: list[str]) -> Inputs:
    github: str | None = a.github
    if a.pr_json:
        pr = read_json(a.pr_json)
    elif github and a.pr:
        pr = fetch_pr(github, a.pr)
    else:
        sys.exit("pass --pr-json, or --github with --pr")
    logins = read_logins(a.logins_json) if a.logins_json else fetch_logins(github, people) if github else {}
    reviews = read_json(a.reviews_json) if a.reviews_json else fetch_reviews(github) if github else []
    loads = read_json(a.loads_json) if a.loads_json else fetch_loads(github, people) if github else {}
    at = iso_ts(a.at) if a.at else int(time.time())
    return Inputs(repo=a.repo, pr=pr, reviews=reviews, logins=logins, loads=loads, at=at)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--map", type=Path, default=Path("REVIEWERS.yml"))
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
    p.add_argument("--check", action="store_true", help="validate REVIEWERS.yml and exit")
    p.add_argument("--workflow", type=Path, help="with --check, compare the map's logins with this allowlist")
    a = p.parse_args(argv)
    m = load_map(a.map)

    if a.check:
        problems = check(m, a.repo, a.workflow)
        print("\n".join(problems) or "REVIEWERS.yml OK")
        return 1 if problems else 0

    inputs = build_inputs(a, sorted(set(map_logins(m).values())))
    result = cascade(m, inputs)
    text = json.dumps(result, indent=1)
    if a.out:
        a.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    if a.summary:
        with a.summary.open("a", encoding="utf-8") as fh:
            fh.write(summary(result, inputs.pr["number"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
