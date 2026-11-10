# System inventory: field sections in the schema viewer

Read on 2026-11-10 from branch `ple-design/schema-viewer-sections` (base
`ple-field-sections-ifc-2729`) and from the demo schema loaded in the local stack.

## Covered

- **Tabs**: react-aria `Tabs` with the viewer's own `TabStyled` and `TabPanelStyled`
  (`entities/schema/ui/styled.tsx`). Properties, Attributes and Relationships stay.
- **Field accordion**: `AccordionStyled` (wraps the legacy
  `shared/components/display/accordion`), with the field label, a kind `Badge` and the
  optional, unique, read-only and computed badges in the title. `PropertyRow` and
  `PropertyTitle` render the property rows.
- **Badges**: legacy `shared/components/ui/badge` with `yellow`, `red`, `blue` and `green`
  variants; the viewer already uses them.
- **Kind links**: `SchemaKindDisplay` renders kinds as badges that open that kind in the
  viewer (`onKindClick`). A "from InfraLagInterface" link can reuse it.
- **Cards**: `@infrahub/ui` `Card` (`card`, `secondary`, `panel` variants), `CardHeader`,
  `CardContent`. `Tooltip` and `Button` from `@infrahub/ui`.
- **Section title**: `SectionTitle` (`entities/nodes/object/ui/object-details/section-title.tsx`),
  label plus muted description, used by the detail page and the form panels.
- **Grouping rule**: `groupFieldsBySection` and `DETAILS_SECTION` / `ADVANCED_SECTION`
  (`entities/nodes/object/...`). The detail page and the forms use it. Reusing it is how the
  viewer matches the detail page (chain link 3).
- **Data**: the schema API returns `containers[]` with `name`, `label`, `description`,
  `order_weight`, `collapsed` and `inherited`, and each attribute and relationship carries
  `container` and `inherited`.

## Close

- **`groupFieldsBySection`** drops sections that hold no fields. The viewer may need to show
  an empty section: InfraLagInterfaceL2 inherits `layer3` but has no field in it.
- **Detail page versus tabs**: the detail page puts a section's attributes and relationships
  in one card (`ObjectDetailsSections` groups `getDataDisplayFields`, which mixes both). The
  viewer splits them across two tabs, so LACP shows `minimum_links` on one tab and `mlag` on
  the other. This is the riskiest assumption in the brief.
- **`inherited`** says a section or field came from a generic but not which one. The source can
  be derived in the frontend: the first generic in `inherit_from` that declares the name, the
  same rule the backend uses. A redeclared field (`mtu` on InfraLagInterfaceL3) has
  `inherited: false`; it is recognised by a generic in `inherit_from` declaring the same name.
- **`ContainersBlock`** (Properties tab) lists each section's properties but not its fields.
- **Panel width**: on `/schema` the viewer is 384px wide, 520px from the `sm` breakpoint, at most
  576px (`pages/schema/list.tsx`). A source label next to each field name has to fit there.

## Missing

- **No `@infrahub/ui` Tabs, Accordion, Disclosure or Badge.** The viewer uses legacy
  components. The prototype keeps them; migrating the viewer is out of scope.
- **No source resolver** for a section or a field. A small helper over the schema store would
  return "declared here", "from <generic>", "redeclared, from <generic>" or "built in".
- **No node with 30+ attributes** in the demo data. The largest is CoreRepository (21
  attributes, 9 relationships). The prototype adds a fixture for this case.
- **No prototype route.** Created in phase 2 (below).

## Sections in the demo data (local stack, branch main)

| Kind | Attributes | Relationships | Sections (inherited) |
|---|---|---|---|
| ExampleSite | 15 | 3 | address, colocation (no) |
| InfraLagInterfaceL2 | 11 | 10 | lacp, layer2, layer3 (yes) |
| InfraLagInterfaceL3 | 10 | 9 | lacp, layer2, layer3 (yes) |
| InfraLagInterface (generic) | 3 | 4 | lacp, layer2, layer3 (no) |
| TemplateInfraLagInterface | 4 | 6 | lacp, layer2, layer3 (no) |

Templates carry sections, so the viewer shows them on template schemas too.

## Prototype mount

Every direction changes only the viewer panel, not the app shell. The prototype mounts inside
the app layout at `/_proto/schema-viewer-sections`, renders the panel at the `/schema` widths,
and passes the history panel `frame`. A kind picker switches between the five test schemas
from the brief; the 30+ attribute case uses a fixture.
