# Brief: instance badge and bar

Source: `dev/specs/007-instance-badge-ifc-3232/spec.md` (IFC-3232, INFP-538). Product framing skipped
because the product card already answers why; grilling skipped because the spec was clarified on
2026-11-04. The five answers below are copied from the spec and the ticket.

- **Done looks like**: on every page, including the login page, a user views a badge with the
  instance label in the top header and a thin colored bar across the top of the page, in the color
  the administrator chose, and the tab title reads `<label> · <page title>`.
- **Who**: anyone who opens the instance: administrators, read-write and read-only users, and
  anonymous visitors on the login page. They just switched from another instance's tab, or they are
  about to change data or upgrade a schema and need to know whether this is production.
- **Riskiest assumption**: that a badge in the header plus a thin bar is noticed before a user acts.
  If users still check the URL, the indicator is too quiet; if it shouts, it steals the header from
  the branch selector and breadcrumb on every page, all day.
- **Out of scope**: favicon upload, login logo upload, activity-log entries for setting changes, any
  guaranteed propagation delay to other open tabs, free hex colors (the color is one of seven presets).
- **Where it's used**: desk. Infrahub's web UI is a desktop application; the sidebar collapses at
  narrow widths, but phones and tablets are not a target. `emil-mobile-native` is skipped.

Fixed by the spec and not up for redesign here: the seven presets (red, amber, green, blue, indigo,
purple, gray), label max 32 characters, independent fields (color only → bar only; label only → gray
badge, no bar), settings edited on the Global preferences page, login page shows the bar and the badge
near the logo.

Left to this jam: the badge's position inside the header, the badge style per color, the bar's
height and style, how the badge sits on the login card, and how the settings section on the Global
preferences page presents the color choice.
