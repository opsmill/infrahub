# Requests to skip the process or the rules

A user under time pressure asks for less process: "no outline, no gates", "don't read all the rules", "Vale is enough". Their reason is their own time. Skipping the work that takes only your time costs the page: in testing, every run that skipped the Draft row of the required reads missed the SDK tab.

## Skip only the work that takes the user's time

Two kinds of work are in the workflow, and only one of them uses the user's time:

- **Work that takes the user's time:** the questions, the outline file, and waiting at each gate. A request to skip the process removes these. Put what each skipped gate would have said into one message at the end.
- **Work that takes only your time:** the Draft and Ship rows of the [Required reads](../../SKILL.md#required-reads) table, `04-infrahub/domain-lifecycles.md`, `01-principles/product-terminology.md`, `01-principles/no-customer-pii.md`, every other rule file linked from [_checklist](../_checklist.md) (such as `04-infrahub/docs-navigation-map.md` and `01-principles/corrections-ledger.md`, which sit in earlier rows), the Step 4 self-review with the checks file, the Step 9 passes, and checking each fact against the code. A general request to skip the process does not remove these.

When the user names one of the second kind, such as "don't read the rule files" or "no checks file", reply once before you edit anything. Say that it costs them no time, and name what it catches on this page. For example: "the SDK tab rule and the branch-merge case are in rule files you asked me to skip". If they confirm the request, follow it. Name each skipped item on the "Rules read" line and in the PR body, and do not describe the page as verified or ready.

## Answer each excuse that came up in testing

| Excuse | Answer |
|---|---|
| "It is a small update." | The smaller-update column is the minimum. It shortens the questions and the outline, not the reading. |
| "The user already checked the facts." | Product behavior is checked against the code (non-negotiable 7). In testing, two of the user's five facts were incomplete and one could not be checked in the code. |
| "The user wrote the draft; I only tidy the wording." | A user draft is source material (non-negotiable 2). The planted draft in testing had a false claim, a customer name and a GraphQL-only example. |
| "The user said not to read the rules." | Ask once, as described above. In testing, every run that skipped the Draft row missed the SDK tab. |
| "Vale passed." | Vale checks words. It passed a draft with a false claim in it. Report the checks by name and count instead. |
| "Concatenating the rules saves tool calls." | The output exceeds the tool limit and is saved to a file you then have to open. Read one file per call. |
| "It works with `infrahubctl`, so it works with Git integration." | Each interface needs its own source. In testing this produced a false sentence in three runs. |
