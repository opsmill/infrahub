# Contracts: proof workflow surfaces

## Trigger contract — `bug-agent-e2e-proof.yml`

- Event: `pull_request` `[opened, synchronize, reopened]`, base `stable`, `paths: tests/e2e/**`.
- Job guard: `startsWith(github.event.pull_request.head.ref, 'ai-bug-pipeline-')`.
- Concurrency group `bug-e2e-proof-<pr>`, `cancel-in-progress: true`.
- Permissions: `contents: write` (release assets), `pull-requests: write` (body PATCH). Never `pull_request_target`.

## Verdict script contract — `.github/scripts/e2e_proof_verdict.py`

```
usage: e2e_proof_verdict.py --phase {red,green} --junit playwright-junit.xml
stdout: verdict=<red_confirmed|green_confirmed|does_not_reproduce|inconclusive>
        reason=<one line>
exit:   0 when the phase contract is satisfied, 1 otherwise
```

Rules (from research R2): RED satisfied only by exactly one testcase whose `<failure>` carries `AssertionError`; `<error>` anywhere, extra/missing testcases, non-assertion failures → `inconclusive`; RED pass → `does_not_reproduce`. GREEN satisfied only by exactly one passing testcase.

## Embed script contract — `.github/scripts/e2e_proof_embed.py`

```
usage: e2e_proof_embed.py --repo <owner/repo> --pr <n> --phase {red,green}
                          --verdict <v> --reason <text> --run-url <url>
                          [--image-url <url>]
```

- Replaces only the content between its own `E2E_PROOF:*` marker pairs; appends missing sections at the end of the body.
- Also rewrites the `E2E_PROOF:NOTE` section per phase (red → expected-red explanation naming the proof job as authoritative; green → note that all jobs are expected to pass).
- MUST leave `AGENT_TEST_COMPLETE` / `AGENT_FIX_COMPLETE` and all content outside the marker pairs byte-identical.
- Idempotent: running twice with the same inputs yields the same body.
- `--reason` is truncated to 200 characters and markdown-neutralized (backticks/brackets/angle-brackets escaped) before insertion (critique E1).

## Asset naming contract

`pr-<pr>-<phase>-<run_id>.png` on release `bug-pipeline-assets`; publisher deletes older `pr-<pr>-<phase>-*` after upload; cleanup workflow (`pull_request` `[closed]`, same branch guard) deletes `pr-<pr>-*`.

## Agent prompt contract (E2E tier addition)

Test-writer, when choosing E2E: place one test under `tests/e2e/<domain>/test_*.py`, module-level `pytestmark = pytest.mark.shard_<name>` (exactly one), do **not** run it locally, push and let `bug-agent-e2e-proof` verify RED. Fix agent: for e2e repro tests, GREEN verification is the proof job, not a local run. On an `inconclusive` verdict the agent does not loop: a human or reviewer re-runs the job, and the test-writer escalates after two consecutive inconclusive runs on the same commit. All other tiers unchanged. Lock files regenerated with `gh aw compile` in the same commit as any `.md` prompt change.
