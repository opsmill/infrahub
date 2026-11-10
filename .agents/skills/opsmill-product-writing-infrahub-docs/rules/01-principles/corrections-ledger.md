# Corrections ledger — user corrections must survive rewrites

When the user corrects a word, a sentence, or a way of framing something, the correction applies to the whole document, not only to the sentence where they made it.

The failure this prevents: a correction returns after a restructure. The user rejects a phrase, it is changed, and two rewrites later it is back — because the restructured text was treated as new writing rather than as writing that already carried corrections.

## The rule

1. **Keep a list of every correction the user makes during the session.** For each one, record the wording they rejected, the wording that replaced it, and the reason behind it — a figurative verb, a feature described as the actor, a vague qualifier. The reason is what applies to other sentences; the exact words are only one example of it.
2. **After any rewrite or restructure, check the whole list against the new text** before showing it to the user. Restructured text is not new text. It inherits every correction already made to it.
3. **Write each entry as a general rule, not a single word.** If the user rejected "objects arrive", record it as "do not use figurative movement verbs for data objects: arrive, land, live, move, flow". Check new writing against the rule, not against the word.
4. **Check the list again during the pre-PR audit** ([Step 9](../02-workflow/step-9-pre-pr-audit.md)), as a pass of its own.

## Why write it down

Over a long session, your attention narrows to the paragraph you are currently writing. A correction made an hour ago, on a paragraph that no longer exists, does not feel relevant to the new paragraph — but it is, because the user was correcting the writing style, not that one paragraph. Writing the corrections down and checking them deliberately is the only approach that still works after a restructure.

## Format

Keep the list wherever the session's working notes are, such as the plan file. One entry per correction:

```text
- Rejected "objects arrive" → "Generators create them / Sync imports them".
  Reason: no figurative verbs. Objects do not arrive, land, or live anywhere.
- Rejected "Object Templates supply structure" → "Choose an Object Template to…".
  Reason: the reader is the subject wherever the reader acts or decides.
- Rejected "pick" → "choose". Reason: house word choice.
```

Searching the new text for the rejected words is a useful first check, but not enough on its own. Read the new text against each reason.
