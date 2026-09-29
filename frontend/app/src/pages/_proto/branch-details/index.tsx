// PROTOTYPE — design-jam harness for .design/branch-details-repos. Variants × frozen revisions,
// driven by the skill's history panel. Delete this directory, its route block in
// src/app/router.tsx, and the designJam() plugin in vite.config.ts once the design is approved.
import { type CSSProperties, useLayoutEffect, useRef, useState } from "react";

import { DesignHistory, type Knob, type KnobValue, type Variant } from "./design-history-panel";
import { CurrentPage } from "./revs/current/current";
import { RevRoot as Rev01, type RevKnobs } from "./revs/rev-01/root";
import { RevRoot as Rev02 } from "./revs/rev-02/root";
import { SCENARIOS, type Scenario } from "./revs/rev-03/data";
import { RevRoot as Rev03 } from "./revs/rev-03/root";
import { RevRoot as Rev04 } from "./revs/rev-04/root";
import { RevRoot as Rev05 } from "./revs/rev-05/root";

const SLUG = "branch-details-repos";

// Knobs belong to the directions they affect: the Current baseline shows no repository data,
// and the rail width only exists in Consistent. Revisions before rev-03 still show Upstream and
// Last import; those fields don't exist in the backend, so the toggle for them was removed.
const DATA_KNOBS: Knob[] = [
  {
    key: "scenario",
    label: "Scenario",
    type: "select",
    options: SCENARIOS.map((s) => s.id),
    value: "incident",
  },
  { key: "repos", label: "Repositories", type: "range", min: 1, max: 40, value: 4 },
  { key: "bands", label: "Error bands before collapsing", type: "range", min: 1, max: 6, value: 3 },
];

const RAIL_KNOB: Knob = {
  key: "rail",
  label: "Rail width",
  type: "range",
  min: 280,
  max: 480,
  step: 10,
  value: 360,
};

const toKnobs = (k: Record<string, KnobValue>): RevKnobs => ({
  scenario: String(k.scenario ?? "incident") as Scenario & RevKnobs["scenario"],
  repos: Number(k.repos ?? 4),
  bands: Number(k.bands ?? 3),
  rail: Number(k.rail ?? 360),
  upstream: k.upstream === undefined ? true : Boolean(k.upstream),
});

const VARIANTS: Variant[] = [
  {
    id: "current",
    label: "Current",
    bet: "Today's page, unchanged — the baseline every direction is compared against.",
    revisions: [
      {
        rev: 1,
        date: "2026-09-23",
        note: "Today's branch details page, without any change from this design.",
        render: () => <CurrentPage />,
      },
    ],
  },
  {
    id: "legacy",
    label: "Legacy",
    bet: "Today's page shape: button row, Tasks accordion of cards, merge banner above the buttons.",
    knobs: DATA_KNOBS,
    revisions: [
      {
        rev: 1,
        date: "2026-09-23",
        note: "Repositories card + merge banner added to today's layout; tasks stay as cards.",
        render: (k) => <Rev01 variant="legacy" knobs={toKnobs(k)} />,
      },
      {
        rev: 2,
        date: "2026-09-29",
        note: "Merge moved into the readiness card; only retrievable data (no Upstream, no Last import, raw error lines).",
        render: (k) => <Rev03 variant="legacy" knobs={toKnobs(k)} />,
      },
    ],
  },
  {
    id: "consistent",
    label: "Consistent",
    bet: "One table pattern everywhere, actions in the header menu, compact merge rail on the right.",
    knobs: [...DATA_KNOBS, RAIL_KNOB],
    revisions: [
      {
        rev: 1,
        date: "2026-09-23",
        note: "Tables for repos and tasks, rail as an index of issues, Actions menu in the header.",
        render: (k) => <Rev01 variant="consistent" knobs={toKnobs(k)} />,
      },
      {
        rev: 2,
        date: "2026-09-29",
        note: "Only retrievable data: no Upstream or Last import, raw error lines, unreachable-remote warning.",
        render: (k) => <Rev03 variant="consistent" knobs={toKnobs(k)} />,
      },
    ],
  },
  {
    id: "object",
    label: "Object layout",
    bet: "Same layers, cards and colours as the object details page; today's inline branch buttons.",
    knobs: DATA_KNOBS,
    revisions: [
      {
        rev: 1,
        date: "2026-09-23",
        note: "Object-page layers; Details as full-width label/value rows (ObjectDataRow).",
        render: (k) => <Rev01 variant="object" knobs={toKnobs(k)} />,
      },
      {
        rev: 2,
        date: "2026-09-23",
        note: "Details back to today's compact attribute grid, inside an object-style card.",
        render: (k) => <Rev02 variant="object" knobs={toKnobs(k)} />,
      },
      {
        rev: 3,
        date: "2026-09-29",
        note: "Only retrievable data: no Upstream or Last import, raw error lines, unreachable-remote warning.",
        render: (k) => <Rev03 variant="object" knobs={toKnobs(k)} />,
      },
      {
        rev: 4,
        date: "2026-09-29",
        note: "No Merge card: today's inline buttons below the repositories; task rows link to their task page; real branch notice, body card scrolls.",
        render: (k) => <Rev04 variant="object" knobs={toKnobs(k)} />,
      },
      {
        rev: 5,
        date: "2026-09-29",
        note: "Task links open a real task: each mocked row uses the id of a real task with the same workflow kind.",
        render: (k) => <Rev05 variant="object" knobs={toKnobs(k)} />,
      },
    ],
  },
];

// The panel is a fixed shell. Pin it to this route's own box (below the app's top bar, right of
// the sidebar), so the real app chrome stays visible and the design renders at its real width.
function useContentFrame() {
  const ref = useRef<HTMLDivElement>(null);
  const [frame, setFrame] = useState<CSSProperties>();

  useLayoutEffect(() => {
    const measure = () => {
      const box = ref.current;
      if (!box) return;
      const r = box.getBoundingClientRect();
      setFrame({
        top: r.top,
        left: r.left,
        right: window.innerWidth - r.right,
        bottom: Math.max(0, window.innerHeight - r.bottom),
        // The shell paints Canvas (white) by default; let the app's own background show through.
        background: "transparent",
      });
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);

  return { ref, frame };
}

function BranchDetailsProto() {
  const { ref, frame } = useContentFrame();
  return (
    <div ref={ref} className="h-full">
      {frame && <DesignHistory slug={SLUG} variants={VARIANTS} frame={frame} />}
    </div>
  );
}

export const Component = BranchDetailsProto;
