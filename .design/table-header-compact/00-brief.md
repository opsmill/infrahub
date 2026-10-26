# Brief — table-header-compact

Run mode: `--fast` (the user asked to "quickly build a few ideas"). Product framing skipped at the user's request. Grilling skipped at the user's request. The answers below are taken from the user's request and the screenshots in `shots/before-*.png`; correct any that are wrong.

- **Done looks like:** on an object's relationship tab, the table starts directly under one row of controls (or none), with no empty row; the repository "On this branch" card header is one line; long field labels wrap left-aligned and stay inside their row.
- **Who hits this:** anyone opening a relationship tab on an object detail page (for example a device's Interfaces tab, which lists a generic, cardinality-many relationship) or the children tab of a hierarchical node (for example a country's Site tab). They arrive from the Details tab of the same object.
- **Riskiest assumption:** that the Add and Columns controls can share one place on every host of the relationship table. The IPAM and repository hosts show the table without an Add button.
- **Out of scope:** the object list view toolbar, the table footer ("15 counts"), and changing which fields appear on the repository card.
- **Where it's used:** desk. The mobile-native pass is skipped.

Source: user request in session, 2026-10-26.
