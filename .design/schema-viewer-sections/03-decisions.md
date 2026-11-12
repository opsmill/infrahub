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
- **Direction picked: the Layout tab, named Containers; the prototype stops here** (2026-11-12,
  Paul). The schema viewer gets a Containers tab between Properties and Attributes. It lists
  each container as an accordion styled like the attribute and relationship accordions, and
  each accordion shows only the container's properties (name, label, description, order
  weight, collapsible, collapsed, inherited), not the fields placed in it. The Properties tab
  stays as it is on develop. Built on the feature branch `ple-field-sections-ifc-2729`, not
  promoted from the prototype.
- **Rejected: changes to the Properties tab** (2026-11-12, Paul). Revisions 1 to 4 put a
  containers block or summary in the Properties tab. Reading the layout of a kind is a
  separate task from reading its properties, so it gets its own tab.
- **Containers gain `collapsible`** (2026-11-12, Paul). Built-in containers (Details,
  Profile, Template) are not collapsible. A user container is collapsible by default, and
  `collapsed` sets whether it starts closed only when it is collapsible.
- **Object page tab renamed from Details to Overview** (2026-11-12, Paul), because the first
  section card inside it is also called Details.
