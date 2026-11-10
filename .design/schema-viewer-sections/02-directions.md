# Directions: field sections in the schema viewer

Prototype: `/_proto/schema-viewer-sections` (local: `http://localhost:8095`, against the stack on
port 8002). Every direction is `dj.rev=1`. The left column lists the test kinds from the brief;
`proto.kind=<kind>` in the URL selects one. All directions keep the panel, the Properties,
Attributes and Relationships tabs and the field accordions.

Shared knob: **Show where each field comes from** (on by default). It adds "from <generic>" or
"redeclared, from <generic>" next to each field. It is a knob because the brief half-builds field
sources, and on InfraLagInterfaceL2 it repeats "from InfraInterface" on seven fields.

Data: the schema of the demo kinds is copied from the local stack into `fixtures.json`, so the
preview works without the demo data. InfraOpticalTransceiverLifecycleAssignment is made up: 34
attributes, a section with one field and a 37-character section label.

## Today (`dj.variant=today`)

The production viewer from the feature branch, unchanged: a Containers block on the Properties
tab, a Container row inside each accordion.

- **Bets on**: nothing new. It is the baseline.
- **Costs**: the reader opens every accordion to find a section's fields, and cannot see where a
  section comes from.

## Grouped lists (`dj.variant=grouped`)

The Attributes and Relationships tabs group their fields under a heading per section, Details
first and Advanced last. The heading shows the label, the source ("built in", "from
InfraLagInterface"), "collapsed" when the section starts collapsed, and the description. A link
on the right, "+ 1 relationship", switches to the same section on the other tab. A declared
section with no field on this tab shows a dashed "No attributes in this section" line. A kind
without sections renders as today.

- **Bets on**: the field tabs stay the place to read fields; the heading does the grouping.
- **Costs**: a section is still split across two tabs; the link only says the other half exists.
  The empty-section line repeats on every tab where a section has no field.
- **Suits**: authors who already use the Attributes tab and want the section next to the field.

## Layout tab (`dj.variant=layout`)

A fourth tab, Layout, between Properties and Attributes. It shows one card per section in detail
page order, with attributes and relationships together and sorted by order weight. Each row has
the label, the field name, the kind or `1 → peer`, the source, and "not in a card on the detail
page" for relationships the detail page leaves out (group memberships, `profiles`, and
many-relationships of kind Generic, Component or Hierarchy). A row opens that field's accordion on its tab.
A declared section with no field says the detail page hides it. The Properties tab replaces the
Containers block with "3 sections, view the layout". A kind without sections has no Layout tab.

- **Bets on**: reading the layout is a different task from reading a field's properties, so it
  gets its own view that mirrors the detail page.
- **Costs**: a fourth tab, and a second list of the same fields. Rows show fewer properties than
  the accordions, so the reader moves between tabs to see both.
- **Suits**: authors checking a generic or a new node before any object exists, which is the
  main reason from the brief.

## Section filter (`dj.variant=filter`)

The Attributes and Relationships lists stay flat. Each accordion title gets a section tag. Chips
above the list ("All 11", "Details 7", "LACP 2", "Layer 3 0") narrow the list to one section, and
the choice carries across both tabs. With a section selected, a strip shows its label, source,
description and "+ 1 in Relationships". A kind without sections has no chips.

- **Bets on**: authors look for one section at a time, so filtering beats grouping.
- **Costs**: "All" shows section membership only as a tag per field, not as a group. The chip
  row wraps on kinds with many sections.
- **Suits**: kinds with many fields where the author already knows which section to check.

## Cut while building

- **A section list on the Properties tab** (each section with its fields underneath) converged
  with the Layout tab: same content, different tab. Kept the Layout tab because it leaves the
  Properties tab for node properties.

## Found while building

- On the detail page, a section's card leaves out some relationships: group memberships,
  `profiles`, and many-relationships of kind Generic, Component or Hierarchy. `ip_addresses` is in Layer 3
  on InfraLagInterfaceL3 but has no row in the Layer 3 card. Only the Layout tab shows this.
- InfraLagInterfaceL2 inherits Layer 3 but has no field in it, and InfraLagInterfaceL3 inherits
  Layer 2 with no field in it. The detail page hides these sections.
