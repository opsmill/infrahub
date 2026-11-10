# Brief: field sections in the schema viewer

Source: the `emil-product-thinking` interview of 2026-11-10. Paul accepted most answers
from the recommended answers offered with each question; his own words are quoted.

Related: feature IFC-2729, spec `dev/specs/ifc-2729-field-sections/spec.md` (FR-026).

## Problem today

The schema viewer shows a flat "Containers" block on the Properties tab (name, label, order
weight, collapsed and description for each section) and a "Container" row inside each
attribute and relationship accordion.

- "we dont know which field is where": to find a section's fields, an author opens every
  accordion one by one.
- "the containers are not displaying in a great ui, visually it's just sections with inline
  rows for the properties".

Today, authors check grouping on an object's detail page and create form, and go back to the
YAML to trace inherited fields.

## The five answers

- **Done looks like**: an author can tell, from the schema viewer alone, which section each
  field of a node or generic is in and where that section comes from, without opening an
  accordion, an object or the YAML.
- **Who**: schema authors checking how a node's detail view and forms will be grouped,
  including sections inherited from generics. They reach the viewer because "generics have
  no objects to check" and because the "schema viewer is here to display the schema
  definitions and containers are part of it".
- **Riskiest assumption**: that a section split across the Attributes and Relationships tabs
  still reads as one section. LACP on InfraLagInterfaceL2 holds `minimum_links` on one tab
  and the `mlag` relationship on the other.
- **Out of scope**:
  - replacing the three tabs (Properties, Attributes, Relationships) with one long page;
  - removing the accordion for each field, with its property rows;
  - changing the side panel, opened from the schema list, or its kind header;
  - the detail page and forms, which the feature branch already covers.
- **Where it's used**: desk only.

A direction may add headings or groups inside a tab, or add a fourth tab. Grouping the
existing Attributes and Relationships lists by section is one direction to try, "but we also
need to keep the current ux".

## Chain of must-be-trues

1. **Under test**: each field's section is visible without opening accordions.
2. Each section's source is visible: declared on the node, inherited from a named generic,
   or built in (Details, Advanced). Each field's source too, including a redeclared field
   (`mtu` on InfraLagInterfaceL3).
3. The viewer's grouping matches the detail page: same order, same fields, Advanced last.
4. Nodes with no sections look the same as today.

## Data every direction is judged on

- InfraLagInterfaceL2: three inherited sections, plus inherited fields with no section.
- InfraLagInterface: the generic that declares LACP, Layer 2 and Layer 3, with no objects.
- InfraLagInterfaceL3: redeclares `mtu` to place it in Layer 3.
- CoreAccount: no sections; must look like today's viewer.
- A node with 30+ attributes and a section holding one field.

## Test

No named testers: Paul said "no need to bother about the testers". Each direction is judged
against these questions on InfraLagInterfaceL2, answered from the viewer alone, without opening
an accordion:

- Which section is `minimum_links` in, and where does that section come from?
- Which other field shares it?

A direction passes if the answers can be read within 30 seconds.

## Skipped passes

- `grilling-ideas` skipped: the product-thinking interview already produced all five answers
  above in one session, with no open pushback.
- `emil-mobile-native` will be skipped in phases 3 and 4: desk only.

## Not decided

- Whether the panel is wide enough to show a source label next to each field name.
- Whether profile and template schemas, which copy sections, also need to show them.
