# Phase 0: Frame

Read this when phase 0 starts. The rules in `SKILL.md` still apply.

Write `00-brief.md` even when both skills are skipped; later phases read it. Record each
skip as its own line in the brief ("product framing skipped at the user's request") and
repeat it at the checkpoint.

| The user says | Skip |
|---|---|
| `--no-product`, "skip the product thinking", "I know why we're building this" | `emil-product-thinking` |
| `--no-grill`, "don't grill me", "just build it" | `grilling-ideas` |
| `--fast`, "straight to prototypes" | both; ask the four questions below once, in one message |

Honour a skip the first time. Do not offer the skipped pass again or bring it back as "a
few quick questions".

1. If `emil-product-thinking` is installed (it is a paid skill), ask the user to type
   `/emil-product-thinking` followed by the request as written: the agent cannot start it. It answers whether this is worth building: what problem it solves, for whom,
   and what happens if nothing is built. If it is not installed, record in the brief that
   product framing was skipped because the skill is not installed.
2. Invoke `grilling-ideas` on the result, unless the idea is already settled: a spec, PRD,
   `.specify/` run or written ticket exists, an earlier `00-brief.md` still holds, or the
   user answers the questions below in one reply without pushback. Then copy the answers
   from that source into the brief, name the source, and say at the checkpoint why you
   skipped.

`grilling-ideas` writes no file, so copy its result into `00-brief.md` yourself. The brief
holds four answers in the user's words:

- **Done looks like**: one sentence on the screen when it works.
- **Who**: who reaches this screen, and what they were doing just before.
- **Riskiest assumption**: the one that makes the screen pointless if it is wrong.
- **Out of scope**: what this is not.

If an answer is vague, say which one and ask again.
