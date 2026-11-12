---
name: what-is-this-pr
description: >-
  Explains simply the purpose of a pull request. TRIGGER when: the user shares a pull request URL or
  number and asks what it is for, what it does or why it exists. DO NOT TRIGGER when: the user wants
  bugs found → reviewing-pull-requests; the user asks what code a pull request does not need →
  simplifying-pull-requests.
argument-hint: <pull request URL or number>
---

# What is this pull request

Explain simply the purpose of the pull request `$ARGUMENTS`:

1. Current state
2. The problem
3. The proposed solution

Explain it from the side of the person who uses the feature, not the implementation: leave out
hook names, query shapes, file paths and test lists. Keep it short.

Read both the description (`gh pr view`) and the code (`gh pr diff`); do not check out the branch.
Descriptions often say more or less than the code does, so explain what the code does, and point
out where the description disagrees with it.
