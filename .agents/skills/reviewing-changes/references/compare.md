# Compare with the PR review

Run after cubic and reviewers have commented on the PR, to find what the local review missed.

1. Read the saved report for the PR's head branch (`gh pr view <n> --json headRefName`). If there
   is none, say so and stop.
2. Collect the PR's comments: inline ones with
   `gh api repos/{owner}/{repo}/pulls/<n>/comments --paginate`, and review bodies and
   conversation comments with `gh pr view <n> --json reviews,comments`. Skip replies, bot status
   messages and comments on lines changed after the report was saved.
3. Classify each comment against the report, by file, line and issue:
   - **Caught**: the report has it under Fixed, Deferred or Advisory.
   - **Declined locally**: the report has it under Declined. Check whether the reason still holds.
   - **Missed**: the report does not have it. Read the code, and decide whether the comment is
     right before counting it. Count a miss on a line the review's own fix changed separately,
     as "introduced by a fix".
4. For each real miss, say which part of the review should have caught it (a rule, an article,
   the design or per-file check, the claims check, the bug review, cubic) and why it did not:
   the rule is missing, the article was not loaded, the file was out of scope, a reviewer had the
   rule and missed it, the claims check did not read the code that produces the claim (for
   example a backend resolver), or a fix introduced it.
5. Report the counts (caught, declined, missed, introduced by a fix, wrong comments), then read
   `.agents/skills/reviewing-changes/references/improve.md` with the Read tool and propose fixes
   as it says. A miss that no rule or document change would prevent becomes a proposed change to
   this skill, for the user to decide.
