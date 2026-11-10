# Decisions

- **The viewer says "container", not "section"** (2026-11-10, Paul, rev 4). The schema viewer
  shows the schema definition, and each Properties row names a schema key in plain words
  ("Inherit from", "Order by"). Authors read it to write `containers:` and `container: lacp`.
  Renaming the schema key to `sections` was considered and rejected: the backend, the SDK, the
  docs and both PRs already use `container`, and nothing user-facing outside the viewer shows
  the word.
- **No built-in Advanced container** (2026-11-10, Paul). `advanced` is an ordinary name; a field
  whose container is not declared stays in Details. Applied to the feature branch and to the
  prototype from rev 3.
- **Field sources off by default** (2026-11-10, Paul, rev 2). The knob stays; container sources
  stay on the headings and rows.
- **Properties tab groups get titles** (2026-11-10, Paul, rev 4). Icon moves from the data group
  to Menu, where it is used.
