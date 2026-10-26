// PROTOTYPE design-jam table-header-compact — route entry; mounts the history panel over the app's content area.
import { type CSSProperties, useLayoutEffect, useRef, useState } from "react";

import type { ObjectKey } from "./data";
import { DesignHistory, type Knob, type KnobValue, type Variant } from "./design-history-panel";
import { type Direction, RelationshipTabRev01 } from "./relationship-tab-rev-01";
import { type BranchHeader, type LabelWrap, RepositoryDetails } from "./repository-details";

const knobs: Knob[] = [
  {
    key: "screen",
    label: "Screen",
    type: "select",
    options: ["relationship-tab", "repository-details"],
    value: "relationship-tab",
  },
  {
    key: "object",
    label: "Object (tab)",
    type: "select",
    options: ["device-interfaces", "country-children", "country-children-empty"],
    value: "device-interfaces",
  },
  { key: "deny", label: "No create permission", type: "toggle", value: false },
  {
    key: "branchHeader",
    label: "Branch card header",
    type: "select",
    options: ["two-lines", "inline", "chip"],
    value: "two-lines",
  },
  {
    key: "labelWrap",
    label: "Field label wrap",
    type: "select",
    options: ["today", "left", "left-balanced"],
    value: "today",
  },
];

const render = (direction: Direction) => (k: Record<string, KnobValue>) =>
  k.screen === "repository-details" ? (
    <RepositoryDetails
      branchHeader={k.branchHeader as BranchHeader}
      labelWrap={k.labelWrap as LabelWrap}
    />
  ) : (
    <RelationshipTabRev01
      direction={direction}
      objectKey={k.object as ObjectKey}
      denyPermission={k.deny as boolean}
    />
  );

const variants: Variant[] = [
  {
    id: "baseline",
    label: "Today",
    bet: "Unchanged: Add and Columns on two stacked right-aligned rows.",
    revisions: [{ rev: 1, note: "Today's layout", date: "2026-10-26", render: render("baseline") }],
  },
  {
    id: "one-row",
    label: "One toolbar row",
    bet: "Same shape as the object list toolbar: table controls on the left, the primary Add on the right.",
    revisions: [
      {
        rev: 1,
        note: "Columns left, Add right, one row",
        date: "2026-10-26",
        render: render("one-row"),
      },
    ],
  },
  {
    id: "tab-strip",
    label: "In the tab strip",
    bet: "No toolbar row at all: the controls sit at the end of the tab strip, the table starts under the tabs.",
    revisions: [
      {
        rev: 1,
        note: "Columns and Add at the right end of the tabs",
        date: "2026-10-26",
        render: render("tab-strip"),
      },
    ],
  },
  {
    id: "where-it-acts",
    label: "Where it acts",
    bet: "Each control moves to what it changes: Columns into the table's header corner, Add into the object header.",
    revisions: [
      {
        rev: 1,
        note: "Columns icon in the header corner, Add in the page header",
        date: "2026-10-26",
        render: render("where-it-acts"),
      },
    ],
  },
];

function TableHeaderCompactProto() {
  const ref = useRef<HTMLDivElement>(null);
  const [frame, setFrame] = useState<CSSProperties>();

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => {
      const r = el.getBoundingClientRect();
      setFrame({
        top: r.top,
        left: r.left,
        width: r.width,
        height: r.height,
        right: "auto",
        bottom: "auto",
      });
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={ref} className="min-h-0 grow">
      {frame && (
        <DesignHistory
          slug="table-header-compact"
          variants={variants}
          knobs={knobs}
          frame={frame}
        />
      )}
    </div>
  );
}

export const Component = TableHeaderCompactProto;
