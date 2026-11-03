# Compare with the pull request review

Run this after cubic and reviewers have commented on the pull request, to find what the local
review missed.

1. Read the saved report for the pull request's head branch
   (`gh pr view <n> --json headRefName`). If there is none, say so and stop.
2. Collect the pull request's comments: the inline ones with
   `gh api repos/{owner}/{repo}/pulls/<n>/comments --paginate`, and the review bodies and
   conversation comments with `gh pr view <n> --json reviews,comments`. Skip replies, bot status
   messages, and comments on lines changed after the report was saved.
3. Classify each comment against the report, by file, line and issue:
   - **Caught**: the report has it under Fixed, Deferred, Pre-existing, Questions for you or
     Advisory.
   - **Declined locally**: the report has it under Declined. Check whether the reason still holds.
   - **Missed**: the report does not have it. Read the code and decide whether the comment is
     right before counting it. When a fix from this review changed the missed line, count it
     separately as "introduced by a fix".
4. For each real miss, name the part of the review that should have caught it (a rule, an
   article, the Approach, Design, New files or Architecture and decisions check, the claims check, the bug
   review, cubic) and why it did not:
   - the rule is missing
   - the article was not loaded
   - the file was out of scope
   - a reviewer had the rule and missed it
   - the claims check did not read the code that produces the claim, for example a backend
     resolver
   - a fix introduced it
5. Report the counts: caught, declined, missed, introduced by a fix, and wrong comments. Then read
   `.agents/skills/reviewing-changes/references/improve.md` with the Read tool and propose
   changes as it says. A miss that no rule or document change would prevent becomes a proposed
   change to this skill, for the user to decide.
