# Round 2 feedback

Source: Paul's message in the session, 2026-11-10, copied word for word:

> default Advanced section should not be there by default anymore, get rid of this and ensure
> specs are up to date with this, it's not related to the prototype but still must be done
>
> for the prototype the hover in layout direction for attributes / relationships in the layout
> tab does not look great
>
> sections part in the first tab oes not look great in all directions that are using it

## Triage

1. **Built-in Advanced section**: addressed in the feature branch (`ple-field-sections-ifc-2729`):
   `advanced` stops being a reserved, built-in section. The prototype follows from rev 3: a
   field whose container is not declared stays in Details (`max_bundle` on the LAG interfaces).
2. **Layout row hover** (Layout tab): addressed in rev 3. No background block any more: the
   field label underlines and the chevron at the end of the row darkens.
3. **Sections block on Properties** (all directions using it): addressed in rev 3. Each section
   is one row in the Properties tab's own row style: label (and "starts collapsed"), a muted
   line with the name and source ("default section", "from <generic>", "declared here"), and the
   field count with a chevron on the right. The description moved out; it shows on the section
   heading or card. Labels are no longer blue links; the whole row opens the section.
