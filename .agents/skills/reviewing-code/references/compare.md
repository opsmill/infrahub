# Compare with the pull request review

Run after reviewers, people or bots, have commented on the pull request, to find what the local
review missed.

1. Read the saved report for the pull request's `headRefName`. If there is none, say so and stop.
2. Collect the comments: inline ones with
   `gh api repos/{owner}/{repo}/pulls/<n>/comments --paginate`, review bodies and conversation
   comments with `gh pr view <n> --json reviews,comments`. Skip replies, bot status messages, and
   comments on lines changed after the report was saved.
3. Classify each comment against the report, by file, line and issue:
   - **Caught**: in Fixed, Deferred, Pre-existing, Questions for you or Advisory.
   - **Declined locally**: in Declined. Check that the reason still holds.
   - **Missed**: not in the report. Read the code to decide whether the comment is right. Count a
     miss on a line a fix changed as "introduced by a fix".
4. For each real miss, name the check that should have caught it and why it did not: the rule is
   missing, the article was not loaded, the file was out of scope, the reviewer missed the rule,
   the claims check did not read the code behind the claim, or a fix introduced it.
5. Report the counts (caught, declined, missed, introduced by a fix, wrong comments), then follow
   `references/improve.md`.
