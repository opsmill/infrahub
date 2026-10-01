// PROTOTYPE design-jam account-settings — the prototype route. Deleted at teardown.

import { type CSSProperties, type ReactNode, useLayoutEffect, useRef, useState } from "react";

import { DesignHistory, type Knob, type Variant } from "./design-history-panel";
import { OverviewRev01 } from "./overview/rev-01";
import { SideNavRev01 } from "./side-nav/rev-01";
import { SinglePageRev01 } from "./single-page/rev-01";
import { TabsRev01 } from "./tabs/rev-01";

const PR_URL: string | undefined = undefined;

const KNOBS: Knob[] = [
  { key: "p2", label: "P2: sections fit their job", type: "toggle", value: true },
  {
    key: "prefs",
    label: "Preferences",
    type: "select",
    options: ["own section", "inside profile"],
    value: "own section",
  },
  {
    key: "tokens",
    label: "Tokens data",
    type: "select",
    options: ["many", "empty", "error", "loading"],
    value: "many",
  },
  {
    key: "password",
    label: "Password",
    type: "select",
    options: ["local", "external"],
    value: "local",
  },
  { key: "admin", label: "Can manage global preferences", type: "toggle", value: true },
  { key: "longName", label: "Long name, no description", type: "toggle", value: false },
];

const DATE = "2026-10-01";

/** Each direction owns its scrolling, so it fills the pane rather than growing it. */
const fill = (node: ReactNode) => <div className="absolute inset-0">{node}</div>;

const VARIANTS: Variant[] = [
  {
    id: "side-nav",
    label: "Side nav",
    bet: "A settings shell with a grouped vertical nav: every section visible, one click apart, room to grow.",
    revisions: [
      {
        rev: 1,
        note: "First cut: grouped side nav, identity on top",
        date: DATE,
        render: (k) => fill(<SideNavRev01 knobs={k} />),
      },
    ],
  },
  {
    id: "tabs",
    label: "Tabs",
    bet: "Keep today's model people already know; fix which tabs exist and what each holds.",
    revisions: [
      {
        rev: 1,
        note: "First cut: today's tabs plus Preferences and Global",
        date: DATE,
        render: (k) => fill(<TabsRev01 knobs={k} />),
      },
    ],
  },
  {
    id: "single-page",
    label: "Single page",
    bet: "Settings are few and short: put them all on one scroll, findable with Ctrl+F.",
    revisions: [
      {
        rev: 1,
        note: "First cut: stacked sections, on-this-page rail",
        date: DATE,
        render: (k) => fill(<SinglePageRev01 knobs={k} />),
      },
    ],
  },
  {
    id: "overview",
    label: "Overview",
    bet: "A landing page that summarises state (expired tokens, theme) before you pick a section.",
    revisions: [
      {
        rev: 1,
        note: "First cut: card grid with live summaries",
        date: DATE,
        render: (k) => fill(<OverviewRev01 knobs={k} />),
      },
    ],
  },
];

/** The panel is fixed-position; it fills the app's content area so the real sidebar and header stay. */
function useContentFrame() {
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
        background: "var(--color-background)",
      });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    window.addEventListener("resize", measure);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, []);

  return [ref, frame] as const;
}

export function Component() {
  const [ref, frame] = useContentFrame();

  return (
    <div ref={ref} className="min-h-0 flex-1">
      {frame && (
        <DesignHistory
          slug="account-settings"
          variants={VARIANTS}
          knobs={KNOBS}
          frame={frame}
          prUrl={PR_URL}
        />
      )}
    </div>
  );
}
