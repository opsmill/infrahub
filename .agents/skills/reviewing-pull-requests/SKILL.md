---
name: reviewing-pull-requests
description: >-
  Reviews a pull request in a separate subagent that has not seen this conversation, applying the
  rules in REVIEW.md. TRIGGER when: this session has just opened a pull request, for example with
  `gh pr create`, or the user asks for a review of a pull request by URL or number. DO NOT TRIGGER
  when: answering existing review comments → addressing-review; watching CI →
  monitoring-pull-requests.
argument-hint: <pull request URL or number>
context: fork
agent: general-purpose
---

Review pull request $ARGUMENTS. You have not seen the conversation that wrote it.

1. Read `REVIEW.md` at the root of the repository. Its rules decide what to report and how to rate it.
2. Run the `code-review` skill with the arguments `xhigh $ARGUMENTS`.
3. Return the findings with the rules in `REVIEW.md` applied, separating the issues this pull request introduces from older ones. Change no files.
