# Review

The page was reviewed on its code by three reviewers on 2026-11-04 (correctness, tests and conventions, design engineering). The visual passes on the running app (`emil-ui-polish`, `emil-surfaces`, `emil-ui-review`, `emil-prep-for-prod`) and the by-hand checks (tab order, dark mode, phone width) have not run yet, because no Infrahub stack ran in this session. The gate is not clean until they do.

## Fixed

- A long IPv6 resource prefix pushed "Weight N" out of the 320px list card; the label now truncates and the weight does not shrink.
- A screen reader read the defaults line as one run-on sentence because the dots are hidden; the line is now a list with one item per phrase.
- The namespace link showed the browser's focus outline instead of the ring the schema links use.
- The empty list said "can't allocate"; it now says "can't allocate prefixes" or "can't allocate addresses".
- The list ordered resource prefixes by weight even when the backend would ignore weights (mixed prefix kinds); it now falls back to prefix order.
- The table requested an extra empty page when the total was an exact multiple of 100.
- The not-found state, the usage percentage formatter and the tooltip message are shared with the number pool page.

## Accepted

- The tooltip of the second bar segment stays "This branch only"; see `03-decisions.md`.
- A shared header component for both pool pages was suggested; deferred, because the two headers differ in their tag and their sentence, and sharing them would touch the number pool page again.
- The prototype's second empty-state line ("once the others with a higher weight are full") is left out, because most IP prefix kinds have no weight.
