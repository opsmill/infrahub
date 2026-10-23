// PROTOTYPE design-jam commits-tab-pending-badge
import { type CSSProperties, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router";

import { DesignHistory, type Variant } from "./design-history-panel";
import { DotRev01 } from "./dot/rev-01";
import { InsideRev01 } from "./inside/rev-01";
import { PillRev01 } from "./pill/rev-01";
import { SCENARIO_OPTIONS } from "./scenarios";
import { TodayRev01 } from "./today/rev-01";
import { WordsRev01 } from "./words/rev-01";

const DATE = "2026-10-23";

const VARIANTS: Variant[] = [
  {
    id: "today",
    label: "Today",
    bet: "Baseline: the grey item-count pill every other tab uses.",
    revisions: [
      {
        rev: 1,
        note: "Baseline from PR #11189, unchanged",
        date: DATE,
        render: (k) => <TodayRev01 scenario={String(k.scenario)} />,
      },
    ],
  },
  {
    id: "pill",
    label: "Pill",
    bet: "Colour and an icon set the count apart from item counts and say import or rebase.",
    revisions: [
      {
        rev: 1,
        note: "Amber pill with an import or branch icon, hidden at 0",
        date: DATE,
        render: (k) => <PillRev01 scenario={String(k.scenario)} />,
      },
    ],
  },
  {
    id: "dot",
    label: "Dot",
    bet: "Presence, not quantity: a dot says something is waiting; the number lives in the tab.",
    knobs: [{ key: "dotSize", label: "Dot size (px)", type: "range", min: 5, max: 10, value: 7 }],
    revisions: [
      {
        rev: 1,
        note: "Static amber dot after the label, number in tooltip and notice",
        date: DATE,
        render: (k) => <DotRev01 scenario={String(k.scenario)} dotSize={Number(k.dotSize)} />,
      },
    ],
  },
  {
    id: "words",
    label: "Words",
    bet: "Words over a number: the label itself says '3 to import' or '2 behind'.",
    revisions: [
      {
        rev: 1,
        note: "Amber words after the label, nothing at 0",
        date: DATE,
        render: (k) => <WordsRev01 scenario={String(k.scenario)} />,
      },
    ],
  },
  {
    id: "inside",
    label: "Inside",
    bet: "Location: the tab bar stays plain and a status strip inside the tab carries the signal.",
    revisions: [
      {
        rev: 1,
        note: "Plain tab, warning strip at the top of the Commits tab",
        date: DATE,
        render: (k) => <InsideRev01 scenario={String(k.scenario)} />,
      },
    ],
  },
];

// The panel shell is fixed-positioned, so it is laid over the box the app layout gives this route.
function useContentFrame() {
  const slotRef = useRef<HTMLDivElement>(null);
  const [frame, setFrame] = useState<CSSProperties | null>(null);

  useEffect(() => {
    const slot = slotRef.current;
    if (!slot) return;

    const measure = () => {
      const rect = slot.getBoundingClientRect();
      setFrame({
        top: rect.top,
        left: rect.left,
        right: window.innerWidth - rect.right,
        bottom: window.innerHeight - rect.bottom,
      });
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(slot);
    window.addEventListener("resize", measure);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, []);

  return { slotRef, frame };
}

function CommitsTabPendingBadgePrototype() {
  const { slotRef, frame } = useContentFrame();
  // Re-renders the panel on every tab click so it writes its dj.* params back after the navigation drops them.
  useLocation();

  return (
    <div ref={slotRef} className="min-h-0 grow">
      {frame && (
        <DesignHistory
          slug="commits-tab-pending-badge"
          variants={VARIANTS}
          knobs={[
            {
              key: "scenario",
              label: "Scenario",
              type: "select",
              options: SCENARIO_OPTIONS,
              value: "all",
            },
          ]}
          frame={frame}
        />
      )}
    </div>
  );
}

export const Component = CommitsTabPendingBadgePrototype;
