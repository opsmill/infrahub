// PROTOTYPE design-jam schema-viewer-sections
import { type CSSProperties, useLayoutEffect, useRef, useState } from "react";

import { DesignHistory, type Knob, type Variant } from "./design-history-panel";
import { FilterRev01 } from "./directions/filter-rev-01";
import { FilterRev02 } from "./directions/filter-rev-02";
import { FilterRev03 } from "./directions/filter-rev-03";
import { GroupedRev01 } from "./directions/grouped-rev-01";
import { GroupedRev02 } from "./directions/grouped-rev-02";
import { GroupedRev03 } from "./directions/grouped-rev-03";
import { LayoutRev01 } from "./directions/layout-rev-01";
import { LayoutRev02 } from "./directions/layout-rev-02";
import { LayoutRev03 } from "./directions/layout-rev-03";
import { TodayRev01 } from "./directions/today-rev-01";

const DATE = "2026-11-10";

const SOURCE_KNOB: Knob = {
  key: "fieldSource",
  label: "Show where each field comes from",
  type: "toggle",
  value: false,
};

const showSource = (k: Record<string, unknown>) => k.fieldSource as boolean;

const VARIANTS: Variant[] = [
  {
    id: "today",
    label: "Today",
    bet: "Baseline: a flat Containers block on Properties and a Container row inside each accordion.",
    revisions: [
      {
        rev: 1,
        note: "Production viewer from the feature branch, unchanged",
        date: DATE,
        render: () => <TodayRev01 />,
      },
    ],
  },
  {
    id: "grouped",
    label: "Grouped lists",
    bet: "Keep the field tabs as the place to read fields; put a section heading over each group, with a link to the same section's fields on the other tab.",
    knobs: [SOURCE_KNOB],
    revisions: [
      {
        rev: 1,
        note: "Section headings inside Attributes and Relationships, empty sections kept",
        date: DATE,
        render: (k) => <GroupedRev01 showFieldSource={showSource(k)} />,
      },
      {
        rev: 2,
        note: "Compact section rows on Properties; field sources off by default",
        date: DATE,
        render: (k) => <GroupedRev02 showFieldSource={showSource(k)} />,
      },
      {
        rev: 3,
        note: "Built-in Advanced section removed; Sections rows restyled as property rows",
        date: DATE,
        render: (k) => <GroupedRev03 showFieldSource={showSource(k)} />,
      },
    ],
  },
  {
    id: "layout",
    label: "Layout tab",
    bet: "A fourth tab previews the detail page: one card per section, attributes and relationships together; field tabs stay as they are.",
    knobs: [SOURCE_KNOB],
    revisions: [
      {
        rev: 1,
        note: "Layout tab with a card per section; a row opens the field's accordion",
        date: DATE,
        render: (k) => <LayoutRev01 showFieldSource={showSource(k)} />,
      },
      {
        rev: 2,
        note: "Cards restyled as viewer accordions; compact section rows on Properties",
        date: DATE,
        render: (k) => <LayoutRev02 showFieldSource={showSource(k)} />,
      },
      {
        rev: 3,
        note: "Built-in Advanced section removed; quieter row hover; Sections rows restyled",
        date: DATE,
        render: (k) => <LayoutRev03 showFieldSource={showSource(k)} />,
      },
    ],
  },
  {
    id: "filter",
    label: "Section filter",
    bet: "Lists stay flat with a section tag on each field; chips narrow both tabs to one section, and the choice carries across tabs.",
    knobs: [SOURCE_KNOB],
    revisions: [
      {
        rev: 1,
        note: "Section chips over Attributes and Relationships, shared selection",
        date: DATE,
        render: (k) => <FilterRev01 showFieldSource={showSource(k)} />,
      },
      {
        rev: 2,
        note: "Compact section rows on Properties; a row filters to that section",
        date: DATE,
        render: (k) => <FilterRev02 showFieldSource={showSource(k)} />,
      },
      {
        rev: 3,
        note: "Built-in Advanced section removed; Sections rows restyled as property rows",
        date: DATE,
        render: (k) => <FilterRev03 showFieldSource={showSource(k)} />,
      },
    ],
  },
];

function SchemaViewerSectionsPrototype() {
  const area = useRef<HTMLDivElement>(null);
  const [frame, setFrame] = useState<CSSProperties>();

  useLayoutEffect(() => {
    const el = area.current;
    if (!el) return;
    const measure = () => {
      const r = el.getBoundingClientRect();
      setFrame({ position: "fixed", top: r.top, left: r.left, width: r.width, height: r.height });
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={area} className="min-h-0 grow">
      {frame && (
        <DesignHistory
          slug="schema-viewer-sections"
          variants={VARIANTS}
          frame={frame}
          prUrl="https://github.com/opsmill/infrahub/pull/11519"
        />
      )}
    </div>
  );
}

export const Component = SchemaViewerSectionsPrototype;
