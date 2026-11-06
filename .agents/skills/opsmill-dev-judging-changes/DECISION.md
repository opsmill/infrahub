# DECISION.md — judging-changes ADRs

Formerly the `quality-gates` shared reference skill. ADR-001 to ADR-004 record the original
design; ADR-005 onwards record the split into standalone skills.

## ADR-001: In-workflow quality gates over louder prompts

**Context:** Every skill `MUST`/`STOP` is a prompt the agent may ignore; the repo has no hook/CI
enforcement. **Decision:** the critical steps become gates (independent verification + evidence +
STOP-on-fail). **Alternatives:** louder markdown (still a prompt); programmatic hooks (Claude-only,
won't port to Codex). **Consequences:** more deliberate friction at critical steps (Pattern 7).
*Amended by ADR-005: the gates still exist, but as skills a workflow invokes rather than steps
embedded in every consumer.*

## ADR-002: Author≠judge via a fresh subagent (P2)

**Context:** a passing self-check proves the author agrees with itself. **Decision:** ship gates
dispatch a fresh subagent given the ORIGINAL criteria (R1), never the author's summary.
**Consequences:** self-certification is impossible at ship gates; ~2x work at those points.

## ADR-003: Hybrid judge by gate purpose

**Decision:** full subagent on irreversible ship gates; lighter fresh-context re-read on
intermediate verify gates. **Consequences:** rigor concentrated where reversal is impossible.
*ADR-005 gives each half its own skill: `opsmill-dev-judging-changes` and
`opsmill-dev-verifying-changes`.*

## ADR-004: opsmill-dev is the canonical copy (R3) — superseded by ADR-006

**Context:** plugins ship independently, so the reference was duplicated. **Decision:**
`opsmill-dev/skills/quality-gates/` was canonical; `opsmill-repo`'s was a synced copy checked by
`scripts/check-quality-gates-sync.sh` in CI. **Superseded:** there is one copy now.

## ADR-005: Gates are standalone skills, not wired into consumers

**Context:** thirteen consumer skills each carried a `## Quality gates` table plus inline
ship/verify blockquotes that loaded `gate-model.md` and the primitives at run time, then
dispatched three judge subagents at every T2 ship point. The judge gates in particular consumed
far more tokens than the workflows they guarded, on every run, whether or not the change
warranted a second reading. The same gate logic is wanted in the spec-kit workflow, where the
embedding pattern would have to be repeated. **Decision:** the ship gate becomes the
user-invocable skill `opsmill-dev-judging-changes` and the verify gate becomes
`opsmill-dev-verifying-changes`. Consumer skills drop their gate tables and blockquotes; shipping
skills keep at most one line pointing at the judge. The gate runs when a user or a workflow step
invokes it, or when a repo has opted into the hook and the deny message sends the agent to the
skill. **Alternatives:** keep the gates embedded but trim the prose (still pays the subagent cost
on every ship); make the judge conditional inside each consumer (thirteen copies of the same
switch). **Consequences:** the default run of a code/PR skill spends nothing on judging; rigour
is a deliberate choice; the trust-tier table becomes guidance for *when to invoke*, not a
declaration each skill must carry; the hook's opt-in flag and receipt path keep their historical
`quality-gates` names so already-opted-in repos are unaffected.

## ADR-006: One copy, in opsmill-dev

**Context:** ADR-004 duplicated the reference into `opsmill-repo` because skills referenced it by
relative path within a plugin. Standalone skills are invoked by name, so cross-plugin relative
paths are no longer needed. **Decision:** the `opsmill-repo` copy, the sync script and its CI job
are removed; the hook is registered only by `opsmill-dev`. `opsmill-repo`'s shipping skill
(`reconciling-repo-drift`) states its traceability and idempotency guardrails directly and may call
the judge by name when `opsmill-dev` is installed. **Consequences:** a repo that installs only
`opsmill-repo` has no receipt enforcement — acceptable, since enforcement belongs with the skill
that produces receipts.

## ADR-007: One judge by default, majority on request

**Context:** N=3 majority judging was mandatory at every T2 ship gate; it tripled the dominant
cost. **Decision:** `opsmill-dev-judging-changes` dispatches one judge unless invoked with
`--majority`, which restores the three-judge, 2+-FAIL rule for high-blast-radius ships. The
receipt records the judge count. **Consequences:** the cheap path is the default; variance
reduction is available where it is worth paying for.
