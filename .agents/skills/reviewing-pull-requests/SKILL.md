---
name: reviewing-pull-requests
description: >-
  Reviews a pull request in a separate subagent that has not seen this conversation, applying the
  rules in REVIEW.md. TRIGGER when: this session has just opened a pull request, for example with
  `gh pr create`; the user asks for a review of a pull request by URL or number; or a hook reports
  that large changes were pushed to a pull request. DO NOT TRIGGER when: answering existing review
  comments → addressing-review; watching CI → monitoring-pull-requests.
argument-hint: <pull request URL or number>
context: fork
agent: general-purpose
---

Review a pull request with the code review built into the tool you are running in, without the
conversation that wrote the change. The pull request is `$ARGUMENTS`; in Codex, take it from the
request that started this skill, or use the pull request of the current branch.

1. Read `REVIEW.md` at the root of the repository. Its rules decide what to report and how to rate
   it.
2. Run the built-in review:
   - **Claude Code:** run the `code-review` skill with the arguments `xhigh <pull request>`.
   - **Codex:** find the base branch with `gh pr view <pull request> --json baseRefName`, or use the
     branch `origin/HEAD` points to when `gh` cannot reach GitHub. Start a new subagent that does
     not get this conversation, give it the task "Review the changes this branch would merge into
     `origin/<base branch>`, following Codex's built-in review instructions in
     `${CODEX_HOME:-$HOME/.codex}/skills/.system/review-agent/SKILL.md`.", and wait for its
     result. Codex does not offer that skill by name, so the subagent reads the file. The pull
     request's branch must be checked out, as it is when this session opened the pull request.
3. Return the findings with the rules in `REVIEW.md` applied, separating the issues this pull
   request introduces from older ones. Change no files.
