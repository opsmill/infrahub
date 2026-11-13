# Prose checks: Enterprise install and Community-to-Enterprise migration

Pages: `install/enterprise.mdx` (new "Before you start" section), `upgrade/community-to-enterprise.mdx` (moved from another branch; the prose walk below covers the earlier draft, not the moved page), `faq/faq.mdx` (one answer), `changelog/+enterprise-migration-docs.added.md`.

## Subject walk (32 sentences)

Each row: subject / verb, and whether the subject can perform the verb.

| # | Subject / verb | Verdict |
|---|---|---|
| E1 | Infrahub Enterprise / is under; (you) request, review | ok |
| E2 | (you) / Request | ok |
| E3 | (you) / Contact; schedule | ok |
| E4 | (you) / Review | ok |
| E5 | OpsMill / publishes | ok |
| E6 | (you) / Confirm; agreements / apply | ok |
| E7 | (you) / Review | ok |
| E8 | Infrahub Enterprise / runs on; Neo4j Enterprise Edition / has | ok |
| E9 | the Docker Compose file / sets | ok, a file sets a configuration value |
| E10 | Setting that variable / is; you / accept | rewritten: was "which accepts that agreement", a value cannot accept |
| E11 | (you) / Read | ok |
| E12 | (you) / Check | ok |
| E13 | (you) / Size | ok |
| E14 | (you) / follow | ok |
| M1 | (you) / Migrate; Enterprise / provides | ok |
| M2 | you / replace; (you) check | rewritten: was "The migration replaces", a process cannot act |
| M3 | (you) / Plan | ok |
| M4 | you / back up, replace, verify, resume | ok |
| M5 | (you) / Choose | ok |
| M6 | you / are moving; (you) plan, change | ok |
| M7 | (you) / Request, confirm, review | ok |
| M8 | Helm / reports; resources / are; which (the report) / does not show | rewritten: was "A successful Helm upgrade confirms", an upgrade cannot confirm |
| M9 | (you) / Enable, configure, test | rewritten: was "Switching editions does not configure", a gerund cannot act; the claim itself was unverified and is dropped |
| M10 | (you) / Confirm; you / changed | ok |
| M11 | (you) / Restore | rewritten with M12: was "Switching images back ... does not restore" |
| M12 | you / switch, roll back, do not restore | ok |
| F1 | fragment "Yes." | ok |
| F2 | Community and Enterprise / share | ok |
| F3 | (you) / back up, replace, check | ok |
| F4 | the guide / has | ok |
| F5 | (you) / See | ok |
| C1 | (the entry) / Added | ok, standard changelog form |

Counts: 32 sentences walked, 6 rewritten (E10, M2, M8, M9, M11, M12).

## Verb walk (29 non-technical verbs)

request, contact, schedule, review, publishes, confirm, apply, runs on, has, sets, accept, read, check, size, follow, migrate, replace, plan, back up, verify, resume, choose, moving, reports, enable, restore, recover, switch, roll back.

One replaced: "arrange" access became "request" access, because "arrange" has several meanings and a reader who knows one of them can mistake what to do. "Runs on" (Neo4j) and "back up" are standard technical terms and stay.

## Naturalness read

Read both pages through. The "Before you start" list has four bullets that each open on a bold imperative; that is the existing shape of the page's other lists, so I left it.

## Mechanical checks

- markdownlint-cli2 on the three changed pages: see the run in the session report.
- Vale: not installed on this machine, so not run.
- `npm run build` in `docs/`: passes, which also checks every internal link.
