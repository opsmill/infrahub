// PROTOTYPE — design-jam harness for .design/branch-details-repos. Variants × frozen revisions,
// driven by the skill's history panel. Delete this directory, its route block in
// src/app/router.tsx, and the designJam() plugin in vite.config.ts once the design is approved.
import { type CSSProperties, useLayoutEffect, useRef, useState } from "react";

import { DesignHistory, type Knob, type KnobValue, type Variant } from "./design-history-panel";
import { RevRoot as Rev01, type RevKnobs } from "./revs/rev-01/root";
import { SCENARIOS, type Scenario } from "./revs/rev-02/data";
import { RevRoot as Rev02 } from "./revs/rev-02/root";

const SLUG = "branch-details-repos";

const KNOBS: Knob[] = [
  {
    key: "scenario",
    label: "Scenario",
    type: "select",
    options: SCENARIOS.map((s) => s.id),
    value: "incident",
  },
  { key: "repos", label: "Repositories", type: "range", min: 1, max: 40, value: 4 },
  { key: "bands", label: "Error bands before collapsing", type: "range", min: 1, max: 6, value: 3 },
  {
    key: "rail",
    label: "Rail width (Consistent)",
    type: "range",
    min: 280,
    max: 480,
    step: 10,
    value: 360,
  },
  { key: "upstream", label: "Upstream + Last import", type: "toggle", value: true },
];

const toKnobs = (k: Record<string, KnobValue>): RevKnobs => ({
  scenario: String(k.scenario) as Scenario,
  repos: Number(k.repos),
  bands: Number(k.bands),
  rail: Number(k.rail),
  upstream: Boolean(k.upstream),
});

const VARIANTS: Variant[] = [
  {
    id: "consistent",
    label: "Consistent",
    bet: "One table pattern everywhere, actions in the header menu, compact merge rail on the right.",
    revisions: [
      {
        rev: 1,
        date: "2026-09-23",
        note: "Tables for repos and tasks, rail as an index of issues, Actions menu in the header.",
        render: (k) => <Rev01 variant="consistent" knobs={toKnobs(k)} />,
      },
    ],
  },
  {
    id: "legacy",
    label: "Legacy",
    bet: "Today's page shape: button row, Tasks accordion of cards, merge banner above the buttons.",
    revisions: [
      {
        rev: 1,
        date: "2026-09-23",
        note: "Repositories card + merge banner added to today's layout; tasks stay as cards.",
        render: (k) => <Rev01 variant="legacy" knobs={toKnobs(k)} />,
      },
    ],
  },
  {
    id: "object",
    label: "Object layout",
    bet: "Same layers, cards and colours as the object details page; Merge is an aside card.",
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
    ],
  },
];

// The panel is a fixed shell; pin it to the app's content area so the real sidebar and top bar
// stay visible and the design renders at its real width.
function useContentFrame() {
  const ref = useRef<HTMLDivElement>(null);
  const [frame, setFrame] = useState<CSSProperties>();

  useLayoutEffect(() => {
    const measure = () => {
      const host = ref.current?.parentElement;
      if (!host) return;
      const r = host.getBoundingClientRect();
      setFrame({
        top: r.top,
        left: r.left,
        right: window.innerWidth - r.right,
        bottom: Math.max(0, window.innerHeight - r.bottom),
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
      {frame && <DesignHistory slug={SLUG} variants={VARIANTS} knobs={KNOBS} frame={frame} />}
    </div>
  );
}

export const Component = BranchDetailsProto;
