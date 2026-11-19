// PROTOTYPE design-jam schema-migrations
import { type CSSProperties, type ReactNode, useLayoutEffect, useRef, useState } from "react";

import { IMPACT_STATES, type ImpactState, WORST_CASE } from "./context";
import { DesignHistory, type Knob, type Revision, type Variant } from "./design-history-panel";
import { CollapsibleSectionsRev01 } from "./directions/collapsible-sections-rev-01";
import { CollapsibleSectionsRev02 } from "./directions/collapsible-sections-rev-02";
import { CollapsibleSectionsRev03 } from "./directions/collapsible-sections-rev-03";
import { CollapsibleSectionsRev04 } from "./directions/collapsible-sections-rev-04";
import { CollapsibleSectionsRev05 } from "./directions/collapsible-sections-rev-05";
import { CollapsibleSectionsRev06 } from "./directions/collapsible-sections-rev-06";
import { CollapsibleSectionsRev07 } from "./directions/collapsible-sections-rev-07";
import { CollapsibleSectionsRev08 } from "./directions/collapsible-sections-rev-08";
import {
  CollapsibleSectionsRev09,
  DATA_STATES,
  type DataState,
  type HeaderOptions,
  IMPACT_PLACES,
  ONE_LIST_SCENES,
  SECTION_DEFAULTS,
  type SectionDefault,
  STAGED_STATES,
  type StagedStatus,
} from "./directions/collapsible-sections-rev-09";

/** The same knobs in every structure, so a screen and a state compare across them. */
const stateKnobs = (scenes: readonly string[]): Knob[] => [
  { key: "view", label: "Screen", type: "select", options: [...scenes], value: scenes[0] ?? "" },
  {
    key: "staged",
    label: "Staged change",
    type: "select",
    options: [...STAGED_STATES],
    value: "staged",
  },
  {
    key: "impact",
    label: "Impact calculation",
    type: "select",
    options: [...IMPACT_STATES],
    value: "done",
  },
  { key: "state", label: "Data", type: "select", options: [...DATA_STATES], value: "loaded" },
  {
    key: "listWidth",
    label: "Schema changes list width",
    type: "range",
    min: 256,
    max: 448,
    step: 16,
    value: 320,
  },
];

// The earlier directions live in git at f946a7c71c; the owner asked for one direction in the panel.
type Scene = (typeof ONE_LIST_SCENES)[number];

// Older revisions do not have the screens and states that rev 8 added, so they show the nearest one.
type OlderScene = Exclude<Scene, "Proposed change: merging" | "Proposed change: merge stopped">;
type OlderStaged = Exclude<StagedStatus, "apply failed">;
const olderScene = (value: unknown): OlderScene => {
  const scene = value as Scene;
  return scene === "Proposed change: merging" || scene === "Proposed change: merge stopped"
    ? "Branch: Schema changes"
    : scene;
};
const olderStaged = (value: unknown): OlderStaged =>
  value === "apply failed" ? "staged" : (value as OlderStaged);

/** Every direction takes the same props, so one Screen and one state compare across them. */
type DirectionProps = {
  scene: OlderScene;
  stagedStatus: OlderStaged;
  toggleStyle: "two levels";
  impactState: ImpactState;
  dataState: DataState;
  listWidth: number;
  setScene: (scene: Scene) => void;
};

const renderWithSections =
  (
    Direction: (props: DirectionProps & { sectionDefault: SectionDefault }) => ReactNode
  ): Revision["render"] =>
  (k, setKnob) => (
    <Direction
      scene={olderScene(k.view)}
      stagedStatus={olderStaged(k.staged)}
      toggleStyle="two levels"
      impactState={k.impact as ImpactState}
      dataState={k.state as DataState}
      listWidth={k.listWidth as number}
      sectionDefault={k.sectionDefault as SectionDefault}
      setScene={(scene) => setKnob("view", scene)}
    />
  );

const sectionKnobs: Knob[] = [
  ...stateKnobs(ONE_LIST_SCENES),
  {
    key: "sectionDefault",
    label: "Schema difference starts",
    type: "select",
    options: [...SECTION_DEFAULTS],
    value: "collapsed when long",
  },
];

/** From rev 5: what the details header shows. */
const headerKnobs: Knob[] = [
  {
    key: "hdrImpact",
    label: "Header: impact calculation",
    type: "select",
    options: [...IMPACT_PLACES],
    value: "in the header",
  },
  {
    key: "hdrStagedOn",
    label: "Header: when staged and on which revision",
    type: "toggle",
    value: true,
  },
  { key: "hdrViewSchema", label: "Header: View the staged schema", type: "toggle", value: true },
  { key: "hdrOperations", label: "Header: number of operations", type: "toggle", value: false },
  { key: "hdrParent", label: "Header: previous schema change", type: "toggle", value: false },
  { key: "hdrLinks", label: "Header: links to the sections", type: "toggle", value: true },
  {
    key: "directLoad",
    label: "Branch: a direct load is running (rev 8)",
    type: "toggle",
    value: false,
  },
  {
    key: "hdrFactsSticky",
    label: "Header: facts stay in view when scrolling (rev 7)",
    type: "toggle",
    value: false,
  },
];

const headerOptions = (k: Record<string, unknown>): HeaderOptions => ({
  factsSticky: k.hdrFactsSticky as boolean,
  impact: k.hdrImpact as HeaderOptions["impact"],
  stagedOn: k.hdrStagedOn as boolean,
  viewSchema: k.hdrViewSchema as boolean,
  operations: k.hdrOperations as boolean,
  parent: k.hdrParent as boolean,
  links: k.hdrLinks as boolean,
});

const DATE = "2026-11-18";

// Earlier directions are in git: Staged tab, Review page and One list revs 1 to 3 at
// ec383abdf9; One list rev 4, Section links and Collapsed kinds at e0dc74065a; Titles at the
// edges, Short sections first and Section tabs at bc67d20136.
const VARIANTS: Variant[] = [
  {
    id: "collapsible-sections",
    label: "Collapsible sections with links",
    bet: "The details panel's header stays in view and links to every section with its count, so nothing is missed; each section opens and closes, and its title stays under the header while it scrolls.",
    knobs: [...sectionKnobs, ...headerKnobs],
    revisions: [
      {
        rev: 1,
        note: "Section titles open and close their section and stay under the details header while it scrolls; a closed section shows its summary; the header of an applied change stays in view too",
        date: DATE,
        render: renderWithSections(CollapsibleSectionsRev01),
      },
      {
        rev: 2,
        note: "Links to every section, with its count, under the name in the header; a link opens a closed section and scrolls to it, and the section in view is highlighted",
        date: DATE,
        render: renderWithSections(CollapsibleSectionsRev02),
      },
      {
        rev: 3,
        note: "No link is highlighted as the current one; a link opens its section, scrolls to it when needed and highlights its title for a moment, so every click shows where it went",
        date: DATE,
        render: renderWithSections(CollapsibleSectionsRev03),
      },
      {
        rev: 4,
        note: "Header links of rev 3 plus section titles that are always on screen (in place, stacked under the header or at the bottom edge), as grey 44 px bars with larger text; Merge into main is a section too; kind card icons stay below the bars",
        date: DATE,
        render: renderWithSections(CollapsibleSectionsRev04),
      },
      {
        rev: 5,
        note: "Header in three bands: the change with its actions, one line of facts with the impact calculation and Recalculate, and the section links with icons; header knobs choose what it shows",
        date: DATE,
        render: (k, setKnob) => (
          <CollapsibleSectionsRev05
            scene={olderScene(k.view)}
            stagedStatus={olderStaged(k.staged)}
            toggleStyle="two levels"
            impactState={k.impact as ImpactState}
            dataState={k.state as DataState}
            listWidth={k.listWidth as number}
            sectionDefault={k.sectionDefault as SectionDefault}
            headerOptions={headerOptions(k)}
            setScene={(scene) => setKnob("view", scene)}
          />
        ),
      },
      {
        rev: 6,
        note: "One type scale: 18 px for the two panel titles, 16 px for section titles, 14 px for card titles and text, 12 px for secondary text; View the staged schema at the end of the links band; no empty band above the first section",
        date: DATE,
        render: (k, setKnob) => (
          <CollapsibleSectionsRev06
            scene={olderScene(k.view)}
            stagedStatus={olderStaged(k.staged)}
            toggleStyle="two levels"
            impactState={k.impact as ImpactState}
            dataState={k.state as DataState}
            listWidth={k.listWidth as number}
            sectionDefault={k.sectionDefault as SectionDefault}
            headerOptions={headerOptions(k)}
            setScene={(scene) => setKnob("view", scene)}
          />
        ),
      },
      {
        rev: 7,
        note: "Review fixes: the facts band scrolls away while the name and the links stay; long names wrap to two lines beside their chip; bars that stay in view are opaque in dark mode; blocked buttons keep their tooltip; each field that would fail lists 10 nodes first; the schema viewer link of a kind is an icon button; plurals for counts of 1",
        date: "2026-11-19",
        render: (k, setKnob) => (
          <CollapsibleSectionsRev07
            scene={olderScene(k.view)}
            stagedStatus={olderStaged(k.staged)}
            toggleStyle="two levels"
            impactState={k.impact as ImpactState}
            dataState={k.state as DataState}
            listWidth={k.listWidth as number}
            sectionDefault={k.sectionDefault as SectionDefault}
            headerOptions={headerOptions(k)}
            setScene={(scene) => setKnob("view", scene)}
          />
        ),
      },
      {
        rev: 8,
        note: "Requirements that rev 7 missed: a staged change blocks the merge; a failed apply; the checks that pass; a merge that runs, and one that stopped, with Roll back; a direct load that runs; runs that left operations out; a cancelled migration; a schema change skipped at merge on main",
        date: "2026-11-19",
        render: (k, setKnob) => (
          <CollapsibleSectionsRev08
            scene={k.view as Scene}
            stagedStatus={k.staged as StagedStatus}
            toggleStyle="two levels"
            impactState={k.impact as ImpactState}
            dataState={k.state as DataState}
            listWidth={k.listWidth as number}
            directLoad={k.directLoad as boolean}
            sectionDefault={k.sectionDefault as SectionDefault}
            headerOptions={headerOptions(k)}
            setScene={(scene) => setKnob("view", scene)}
          />
        ),
      },
      {
        rev: 9,
        note: "In a proposed change, the Schema changes list stays at the top while the tab scrolls, with its own scroll, like the details header beside it",
        date: "2026-11-19",
        render: (k, setKnob) => (
          <CollapsibleSectionsRev09
            scene={k.view as Scene}
            stagedStatus={k.staged as StagedStatus}
            toggleStyle="two levels"
            impactState={k.impact as ImpactState}
            dataState={k.state as DataState}
            listWidth={k.listWidth as number}
            directLoad={k.directLoad as boolean}
            sectionDefault={k.sectionDefault as SectionDefault}
            headerOptions={headerOptions(k)}
            setScene={(scene) => setKnob("view", scene)}
          />
        ),
      },
    ],
  },
];

const ROUND_ONE_SCOPES = ["branch-tab", "schema-page", "review"].map(
  (variant) => `design-jam:notes:schema-migrations:${variant}:rev1`
);
const ROUND_ONE_CLEARED = "design-jam:schema-migrations:round-1-cleared";

// Round 1 notes are copied to .design/schema-migrations/feedback/round-1.md, so the pins are removed once per browser.
function clearRoundOneNotes() {
  try {
    if (localStorage.getItem(ROUND_ONE_CLEARED)) return;
    for (const key of ROUND_ONE_SCOPES) localStorage.removeItem(key);
    localStorage.setItem(ROUND_ONE_CLEARED, new Date().toISOString());
  } catch {
    /* storage blocked: the notes stay, nothing else depends on it */
  }
}

// Runs before the panel reads the notes on its first render.
clearRoundOneNotes();

function SchemaMigrationsPrototype() {
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
      {frame && <DesignHistory slug="schema-migrations" variants={VARIANTS} frame={frame} />}
      <DataSetToggle />
    </div>
  );
}

// PROTOTYPE design-jam schema-migrations: break-ui's data toggle, chrome rather than design.
const DATA_SETS = [
  { id: "demo", label: "Demo data" },
  { id: "worst", label: "Worst case" },
] as const;

/** The records are read once when the page loads, so switching reloads it. */
function DataSetToggle() {
  const active = WORST_CASE ? "worst" : "demo";
  const select = (id: string) => {
    if (id === active) return;
    const next = new URLSearchParams(window.location.search);
    if (id === "worst") next.set("dj.data", "worst");
    else next.delete("dj.data");
    window.location.search = next.toString();
  };
  return (
    <div
      role="radiogroup"
      aria-label="Data set"
      style={{
        position: "fixed",
        bottom: 12,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 50,
        display: "flex",
        gap: 2,
        padding: 2,
        borderRadius: 999,
        background: "#e5e5e5",
        boxShadow: "0 1px 3px rgb(0 0 0 / 0.15)",
        font: "12px system-ui, sans-serif",
      }}
    >
      {DATA_SETS.map((d) => (
        <button
          key={d.id}
          type="button"
          role="radio"
          aria-checked={d.id === active}
          onClick={() => select(d.id)}
          style={{
            padding: "4px 12px",
            borderRadius: 999,
            border: 0,
            cursor: "pointer",
            color: "#171717",
            background: d.id === active ? "#fff" : "transparent",
            boxShadow: d.id === active ? "0 1px 2px rgb(0 0 0 / 0.15)" : "none",
          }}
        >
          {d.label}
        </button>
      ))}
    </div>
  );
}

export const Component = SchemaMigrationsPrototype;
