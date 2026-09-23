/**
 * Prototype-only chrome for a design-jam run. Not product UI, not reviewed, not shipped.
 *
 * Deliberately built from plain elements and inline styles rather than @infrahub/ui: the
 * panel sits on top of the design being reviewed, and anything built from the same design
 * system competes with it for attention and muddies the review.
 *
 * Does four things: switch between directions, scrub through revisions, tune exposed
 * values without an agent round trip, and collect pinned feedback to hand back.
 *
 * Copy into the prototype route's folder and adapt. See SKILL.md § The history panel and
 * § Iterating inside the prototype.
 *
 * Adapted for branch-details-repos: `frame` pins the fixed shell to the app's content area
 * instead of the whole window, so the real sidebar and top bar stay visible and the design
 * keeps its real width. The shell still owns that area; the design scrolls inside its pane.
 */

import { type CSSProperties, type ReactNode, useEffect, useState } from "react";

import { Annotations, markSent, type Note, notesToMarkdown } from "./design-annotations";

export type KnobValue = number | string | boolean;

export type Knob =
  | {
      key: string;
      label: string;
      type: "range";
      min: number;
      max: number;
      step?: number;
      value: number;
    }
  | { key: string; label: string; type: "color"; value: string }
  | { key: string; label: string; type: "toggle"; value: boolean }
  | { key: string; label: string; type: "select"; options: string[]; value: string };

export type Revision = {
  /** 1-based, append-only. Never renumber. */
  rev: number;
  /** One line, past tense: what changed in this revision. */
  note: string;
  date: string;
  render: (knobs: Record<string, KnobValue>) => ReactNode;
};

export type Variant = {
  /** Stable slug used in the URL. Never rename once shared. */
  id: string;
  label: string;
  /** What this direction bets on, from 02-directions.md. */
  bet: string;
  /**
   * Knobs that only make sense for this direction. A split-pane's divider position is
   * meaningless in a stacked layout; showing it there gives the user a control that does
   * nothing, which reads as a broken prototype rather than an inapplicable option.
   * A key declared here overrides a shared key of the same name.
   */
  knobs?: Knob[];
  revisions: Revision[];
};

type Props = {
  slug: string;
  variants: Variant[];
  /** Knobs that apply to every direction. Exposing one is a design decision — be sparing. */
  knobs?: Knob[];
  /** Fixed-position box the shell fills. Defaults to the whole viewport. */
  frame?: CSSProperties;
};

export function DesignHistory({ slug, variants, knobs: shared = [], frame }: Props) {
  const params = new URLSearchParams(window.location.search);

  /** Every knob any direction could show — so switching never lands on an undefined value. */
  const allKnobs = [...shared, ...variants.flatMap((v) => v.knobs ?? [])];

  const initialVariant = (variants.find((v) => v.id === params.get("variant")) ??
    variants[0]) as Variant;
  const latestOf = (v: Variant) => v.revisions.at(-1)?.rev ?? 1;

  const [variantId, setVariantId] = useState(initialVariant.id);
  const [rev, setRev] = useState(() => {
    const asked = Number(params.get("rev"));
    return Number.isFinite(asked) && asked > 0 ? asked : latestOf(initialVariant);
  });
  const [compareWith, setCompareWith] = useState<number | null>(() => {
    const asked = Number(params.get("compare"));
    return Number.isFinite(asked) && asked > 0 ? asked : null;
  });
  const [values, setValues] = useState<Record<string, KnobValue>>(() =>
    Object.fromEntries(
      allKnobs.map((k) => {
        const raw = params.get(`k.${k.key}`);
        if (raw === null) return [k.key, k.value];
        if (k.type === "range") return [k.key, Number(raw)];
        if (k.type === "toggle") return [k.key, raw === "1"];
        return [k.key, raw];
      })
    )
  );

  const [open, setOpen] = useState(true);
  const [knobsOpen, setKnobsOpen] = useState(false);
  const [armed, setArmed] = useState(false);
  const [notes, setNotes] = useState<Note[]>([]);
  const [sentTick, setSentTick] = useState(0);
  const [saved, setSaved] = useState("");

  const variant = (variants.find((v) => v.id === variantId) ?? variants[0]) as Variant;
  const latest = latestOf(variant);
  const current =
    variant.revisions.find((r) => r.rev === rev) ?? (variant.revisions.at(-1) as Revision);
  const other = compareWith ? (variant.revisions.find((r) => r.rev === compareWith) ?? null) : null;
  const stale = current.rev !== latest;
  const scope = `${slug}:${variant.id}:rev${current.rev}`;

  /** Only what this direction actually reads. A variant key shadows a shared one. */
  const own = variant.knobs ?? [];
  const ownKeys = new Set(own.map((k) => k.key));
  const inherited = shared.filter((k) => !ownKeys.has(k.key));
  const knobs = [...inherited, ...own];
  /**
   * The render function receives only the active subset, never the whole map. If a
   * revision reaches for a knob belonging to another direction it gets `undefined` and
   * breaks loudly, instead of silently reading a value that no visible control changes.
   */
  const activeValues = Object.fromEntries(knobs.map((k) => [k.key, values[k.key]]));
  const written = notes.filter((n) => n.text.trim() && !n.sentAt).length;
  const alreadySent = notes.filter((n) => n.sentAt).length;

  useEffect(() => {
    const next = new URLSearchParams(window.location.search);
    next.set("variant", variant.id);
    next.set("rev", String(current.rev));
    if (other) next.set("compare", String(other.rev));
    else next.delete("compare");
    // Only the active knobs go in the URL; a link never carries a control the recipient
    // won't see on the direction it opens.
    for (const k of allKnobs) next.delete(`k.${k.key}`);
    for (const k of knobs) {
      const v = values[k.key];
      next.set(`k.${k.key}`, typeof v === "boolean" ? (v ? "1" : "0") : String(v));
    }
    window.history.replaceState(null, "", `?${next.toString()}`);
  }, [variant.id, current.rev, other, values, knobs, allKnobs]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (el && /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) return;
      if (e.key === "Escape") setArmed(false);
      if (e.key === "ArrowLeft") setRev((r) => Math.max(1, r - 1));
      if (e.key === "ArrowRight") setRev((r) => Math.min(latest, r + 1));
      if (e.key.toLowerCase() === "l") setRev(latest);
      if (e.key.toLowerCase() === "h") setOpen((o) => !o);
      if (e.key.toLowerCase() === "k") setKnobsOpen((k) => !k);
      if (e.key.toLowerCase() === "a") setArmed((a) => !a);
      if (e.key.toLowerCase() === "c") setCompareWith((c) => (c === null ? latest : null));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [latest]);

  const pickVariant = (id: string) => {
    const v = variants.find((x) => x.id === id);
    if (!v) return;
    setVariantId(id);
    setRev(latestOf(v));
    setCompareWith(null);
  };

  const asMarkdown = () => {
    const knobLines = knobs
      .map(
        (k) =>
          `- ${k.label} (\`${k.key}\`): ${values[k.key]}${
            ownKeys.has(k.key) ? ` — ${variant.label} only` : ""
          }`
      )
      .join("\n");
    return [
      `## design-jam feedback — ${slug} · ${variant.label} · rev ${current.rev}`,
      knobs.length ? `\n### Knobs\n${knobLines}` : "",
      `\n### Notes\n${notesToMarkdown(notes) || "_No notes._"}`,
    ].join("\n");
  };

  const flash = (msg: string) => {
    setSaved(msg);
    setTimeout(() => setSaved(""), 2600);
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(asMarkdown());
      flash("✓ Copied — paste it to your agent");
    } catch {
      flash("Clipboard blocked by the browser");
    }
  };

  /**
   * The submit. Writes to `.design/<slug>/` through the dev plugin so the agent's next turn
   * reads a file; falls back to the clipboard when there's no dev server behind the page,
   * which is every teammate opening the shared link. Feedback never dead-ends.
   */
  const send = async () => {
    let landed = "";
    try {
      const res = await fetch("/__design-jam/save", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          slug,
          variant: variant.id,
          rev: current.rev,
          knobs: values,
          notes: notesToMarkdown(notes),
        }),
      });
      // Never trust `res.ok` alone. With the plugin unregistered, Vite's SPA fallback
      // answers this URL with 200 and index.html — a "sent" that wrote nothing, which is
      // exactly the failure that looks like success.
      const data = await res.json().catch(() => null);
      if (res.ok && data?.designJam) landed = data.path;
    } catch {
      /* no dev server — fall through to the clipboard */
    }

    if (!landed) {
      await copy();
      return;
    }

    markSent(scope);
    setSentTick((t) => t + 1);
    flash(`✓ Sent — written to ${landed}`);
  };

  const pane = (r: Revision, tag: string | null, annotate: boolean) => (
    <section className="djh-pane">
      {tag && <header className="djh-pane-tag">{tag}</header>}
      {annotate ? (
        <Annotations
          scope={scope}
          refreshKey={sentTick}
          armed={armed}
          onArmedChange={setArmed}
          onNotesChange={setNotes}
        >
          {r.render(activeValues as Record<string, KnobValue>)}
        </Annotations>
      ) : (
        r.render(activeValues as Record<string, KnobValue>)
      )}
    </section>
  );

  return (
    <div className="djh-root" style={frame}>
      <style>{css}</style>

      {stale && (
        <div className="djh-stale" role="status">
          Viewing revision {current.rev} of {latest} — this is not the current design.
          <button type="button" onClick={() => setRev(latest)}>
            Jump to latest
          </button>
        </div>
      )}

      <div className={other ? "djh-stage djh-stage--split" : "djh-stage"}>
        {pane(current, other ? `rev ${current.rev}` : null, true)}
        {other && pane(other, `rev ${other.rev}`, false)}
      </div>

      <div className="djh-dock">
        {open && knobsOpen && knobs.length > 0 && (
          <div className="djh-knobs">
            {knobs.map((k, i) => (
              // biome-ignore lint/a11y/noLabelWithoutControl: every branch below renders the wrapped control
              <label
                key={k.key}
                className={
                  i === inherited.length && own.length > 0
                    ? "djh-knob djh-knob--first-own"
                    : "djh-knob"
                }
              >
                {i === inherited.length && own.length > 0 && (
                  <span className="djh-knob-group">{variant.label} only</span>
                )}
                <span>{k.label}</span>
                {k.type === "range" && (
                  <span className="djh-knob-range">
                    <input
                      type="range"
                      min={k.min}
                      max={k.max}
                      step={k.step ?? 1}
                      value={Number(values[k.key])}
                      onChange={(e) => setValues({ ...values, [k.key]: Number(e.target.value) })}
                    />
                    <output>{String(values[k.key])}</output>
                  </span>
                )}
                {k.type === "color" && (
                  <input
                    type="color"
                    value={String(values[k.key])}
                    onChange={(e) => setValues({ ...values, [k.key]: e.target.value })}
                  />
                )}
                {k.type === "toggle" && (
                  <input
                    type="checkbox"
                    checked={Boolean(values[k.key])}
                    onChange={(e) => setValues({ ...values, [k.key]: e.target.checked })}
                  />
                )}
                {k.type === "select" && (
                  <select
                    value={String(values[k.key])}
                    onChange={(e) => setValues({ ...values, [k.key]: e.target.value })}
                  >
                    {k.options.map((o) => (
                      <option key={o} value={o}>
                        {o}
                      </option>
                    ))}
                  </select>
                )}
              </label>
            ))}
            <button
              type="button"
              className="djh-btn"
              onClick={() =>
                setValues({
                  ...values,
                  ...Object.fromEntries(knobs.map((k) => [k.key, k.value])),
                })
              }
            >
              Reset values
            </button>
          </div>
        )}

        {open ? (
          <div className="djh-bar">
            <section className="djh-zone">
              <span className="djh-zone-label">Prototype</span>
              <div className="djh-seg" role="group" aria-label="Prototype direction">
                {variants.map((v) => (
                  <button
                    key={v.id}
                    type="button"
                    title={v.bet}
                    aria-pressed={v.id === variant.id}
                    className={v.id === variant.id ? "djh-seg-btn djh-seg-btn--on" : "djh-seg-btn"}
                    onClick={() => pickVariant(v.id)}
                  >
                    {v.label}
                  </button>
                ))}
              </div>
            </section>

            <section className="djh-zone djh-zone--grow">
              <span className="djh-zone-label">
                Revision <b className="djh-count">{current.rev}</b>
                <span className="djh-of">of {latest}</span>
              </span>
              <div className="djh-row">
                <button
                  type="button"
                  className="djh-icon"
                  aria-label="Previous revision"
                  disabled={current.rev <= 1}
                  onClick={() => setRev(current.rev - 1)}
                >
                  ‹
                </button>
                <input
                  className="djh-scrub"
                  type="range"
                  min={1}
                  max={latest}
                  step={1}
                  value={current.rev}
                  aria-label="Revision"
                  onChange={(e) => setRev(Number(e.target.value))}
                />
                <button
                  type="button"
                  className="djh-icon"
                  aria-label="Next revision"
                  disabled={current.rev >= latest}
                  onClick={() => setRev(current.rev + 1)}
                >
                  ›
                </button>
              </div>
              <p className="djh-note" title={current.date}>
                {current.note}
              </p>
            </section>

            <section className="djh-zone">
              <span className="djh-zone-label">View</span>
              <div className="djh-row">
                {knobs.length > 0 && (
                  <button
                    type="button"
                    aria-pressed={knobsOpen}
                    className={knobsOpen ? "djh-btn djh-btn--on" : "djh-btn"}
                    onClick={() => setKnobsOpen(!knobsOpen)}
                  >
                    Knobs
                  </button>
                )}
                <button
                  type="button"
                  aria-pressed={Boolean(other)}
                  className={other ? "djh-btn djh-btn--on" : "djh-btn"}
                  onClick={() => setCompareWith(other ? null : latest)}
                >
                  Compare
                </button>
                <button
                  type="button"
                  className="djh-btn"
                  disabled={!stale}
                  onClick={() => setRev(latest)}
                >
                  Latest
                </button>
                <button type="button" className="djh-btn" onClick={() => setOpen(false)}>
                  Hide
                </button>
              </div>
            </section>

            <section className="djh-zone djh-zone--act">
              <span className="djh-zone-label">Feedback</span>
              <div className="djh-row">
                <button
                  type="button"
                  aria-pressed={armed}
                  className={armed ? "djh-btn djh-btn--on" : "djh-btn"}
                  onClick={() => setArmed(!armed)}
                >
                  {armed ? "Click the spot…" : "Add note"}
                  {!armed && written > 0 && <span className="djh-badge">{written}</span>}
                </button>
                <button type="button" className="djh-btn" onClick={copy}>
                  Copy
                </button>
                <button
                  type="button"
                  className="djh-btn djh-btn--primary"
                  disabled={written === 0}
                  onClick={send}
                >
                  {written === 0
                    ? alreadySent > 0
                      ? "All sent"
                      : "Send"
                    : `Send ${written} ${written === 1 ? "note" : "notes"}`}
                </button>
              </div>
            </section>

            {saved && (
              <p className="djh-flash" role="status">
                {saved}
              </p>
            )}
          </div>
        ) : (
          <button
            type="button"
            className="djh-fab"
            aria-label={`Show design panel — ${variant.label}, revision ${current.rev}`}
            onClick={() => setOpen(true)}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true" width="20" height="20">
              <g fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                <path d="M4 8h10M18 8h2M4 16h4M12 16h8" />
                <circle cx="16" cy="8" r="2" fill="currentColor" stroke="none" />
                <circle cx="10" cy="16" r="2" fill="currentColor" stroke="none" />
              </g>
            </svg>
            {written > 0 && <span className="djh-badge djh-badge--fab">{written}</span>}
          </button>
        )}
      </div>
    </div>
  );
}

const css = `
/*
 * The panel owns the viewport: one fixed shell, the design scrolls inside it, the bar is a
 * sibling rather than an overlay. A fixed bar floating over a normally-scrolling page is
 * what produces dead space under the design and a page that scrolls out from under the
 * controls — this structure makes both impossible.
 */
.djh-root {
  position: fixed; inset: 0; z-index: 10;
  display: flex; flex-direction: column;
  padding-bottom: env(safe-area-inset-bottom, 0px);
  background: Canvas;
}
.djh-stale {
  flex: none;
  display: flex; align-items: center; gap: 12px;
  padding: 8px 16px;
  font: 500 13px/1.4 system-ui, sans-serif;
  color: #431407; background: #fed7aa; border-bottom: 1px solid #fb923c;
}
.djh-stale button {
  font: inherit; cursor: pointer;
  padding: 3px 9px; border-radius: 4px;
  border: 1px solid #9a3412; background: transparent; color: #7c2d12;
}
.djh-stage {
  flex: 1 1 auto; min-height: 0;
  display: grid; grid-template-columns: 1fr;
}
.djh-stage--split { grid-template-columns: 1fr 1fr; }
.djh-stage--split .djh-pane + .djh-pane { border-left: 1px solid rgba(128,128,128,.35); }
.djh-pane {
  min-width: 0; min-height: 0;
  overflow: auto; overscroll-behavior: contain;
}
.djh-pane-tag {
  position: sticky; top: 0; z-index: 30;
  padding: 4px 12px;
  font: 600 11px/1.4 ui-monospace, monospace; letter-spacing: .08em; text-transform: uppercase;
  color: #fff; background: #1f2937;
}
/*
 * The tools float over the design rather than sitting in its layout: the design is the
 * thing being judged, so it gets the whole frame, and the panel is visibly an instrument
 * laid on top of it. The dock itself is click-through; only the panels inside it aren't.
 */
/* Anchored bottom-right at a fixed width, sections stacked. A full-width bar spanning the
   viewport competes with the design for the eye; a corner panel is read as a tool. */
.djh-dock {
  position: absolute; right: 16px; z-index: 50;
  bottom: calc(16px + env(safe-area-inset-bottom, 0px));
  width: 304px; max-width: calc(100% - 32px);
  display: flex; flex-direction: column; align-items: stretch; gap: 8px;
  pointer-events: none;
}
.djh-dock > * { pointer-events: auto; }

.djh-knobs {
  display: flex; flex-direction: column; align-items: stretch; gap: 9px;
  max-height: 46vh; overflow-y: auto; overscroll-behavior: contain;
  padding: 12px 14px; border-radius: 12px;
  font: 500 12px/1.4 system-ui, sans-serif; color: #e4e4e7;
  background: #232329;
  box-shadow: 0 0 0 1px rgba(255,255,255,.07), 0 10px 30px -8px rgba(0,0,0,.55);
}
.djh-knob {
  display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 4px 10px;
}
.djh-knob > span { color: #a1a1aa; min-width: 0; }
.djh-knob input, .djh-knob select { justify-self: end; }
/* A visible seam, so it is obvious which controls belong to this direction alone. */
.djh-knob--first-own { margin-top: 5px; padding-top: 11px; border-top: 1px solid #3a3a42; }
.djh-knob-group {
  grid-column: 1 / -1;
  font-size: 9px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase;
  color: #7c7c86;
}
.djh-knob-range { display: flex; align-items: center; gap: 8px; justify-self: end; }
.djh-knob output { min-width: 3ch; text-align: right; font-variant-numeric: tabular-nums; }
.djh-knob input[type="range"] { width: 118px; accent-color: #6366f1; }
.djh-knob select {
  font: inherit; padding: 3px 6px; border-radius: 5px;
  color: #e4e4e7; background: #3f3f46; border: 1px solid rgba(255,255,255,.14);
}
/*
 * Four labelled zones, separated by hairline rules rather than guesswork about gaps:
 * what you are looking at (Prototype), when (Revision), how you look at it (View), and
 * what you send back (Feedback). One primary action in the whole bar — Send — so the
 * submit is never ambiguous; everything else is a quiet ghost button.
 *
 * On a dark surface, separation is a solid quiet line: translucent white hairlines glow
 * instead of receding.
 */
.djh-bar {
  --line: #2b2b31;
  --txt: #e8e8ea;
  --dim: #8b8b93;
  --accent: #5b5bd6;
  --hair: 1px;
  display: flex; flex-direction: column; align-items: stretch; gap: 0;
  padding: 4px 0; border-radius: 14px; overflow: hidden;
  font: 500 12px/1.4 system-ui, sans-serif; color: var(--txt);
  background: #16161a;
  box-shadow: 0 0 0 1px rgba(255,255,255,.08), 0 12px 34px -8px rgba(0,0,0,.6);
}
@media (min-resolution: 192dpi) { .djh-bar { --hair: 0.5px; } }

/* Collapsed: one circle, bottom-right, carrying the unsent-note count. */
.djh-fab {
  align-self: flex-end;
  position: relative;
  display: flex; align-items: center; justify-content: center;
  width: 44px; height: 44px; border-radius: 999px;
  cursor: pointer; color: #e8e8ea; background: #16161a; border: none;
  box-shadow: 0 0 0 1px rgba(255,255,255,.08), 0 10px 26px -6px rgba(0,0,0,.6);
}
.djh-fab:hover { background: #202027; }
.djh-fab:focus-visible { outline: 2px solid #a5b4fc; outline-offset: 2px; }

.djh-zone {
  display: flex; flex-direction: column; gap: 6px;
  min-width: 0; padding: 9px 14px;
}
.djh-zone + .djh-zone { border-top: var(--hair) solid var(--line); }
/* The zone you act from sits fractionally above the rest of the panel. */
.djh-zone--act { background: rgba(255,255,255,.035); }
.djh-zone-label {
  display: flex; align-items: baseline; gap: 5px;
  font-size: 9px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase;
  color: var(--dim);
}
.djh-count { color: var(--txt); font-variant-numeric: tabular-nums; }
.djh-of { font-weight: 600; letter-spacing: .06em; }
.djh-row { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; min-width: 0; }

/* Segmented control: one object, so the directions read as alternatives, not as four
   unrelated buttons. Inner radius = outer (7) − padding (2). */
.djh-seg {
  display: grid; grid-auto-flow: column; grid-auto-columns: 1fr;
  gap: 2px; padding: 2px; border-radius: 8px;
  background: rgba(255,255,255,.06);
}
.djh-seg-btn {
  font: inherit; cursor: pointer;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  min-height: 24px; padding: 3px 8px; border-radius: 6px;
  color: var(--dim); background: transparent; border: none;
}
.djh-seg-btn:hover { color: var(--txt); }
.djh-seg-btn--on { color: #fff; background: rgba(255,255,255,.14); }

.djh-btn, .djh-icon {
  font: inherit; cursor: pointer; white-space: nowrap;
  display: inline-flex; align-items: center; gap: 6px;
  min-height: 26px; padding: 4px 10px; border-radius: 6px;
  color: var(--txt); background: rgba(255,255,255,.07); border: none;
}
.djh-icon { padding: 2px 8px; font-size: 15px; line-height: 1.2; }
.djh-btn:hover:not(:disabled), .djh-icon:hover:not(:disabled) { background: rgba(255,255,255,.14); }
.djh-btn:active:not(:disabled), .djh-icon:active:not(:disabled) { transform: translateY(0.5px); }
.djh-btn--on { color: #fff; background: var(--accent); }
/* The submit takes its own full-width line: it is the one primary action, and it must not
   be mistaken for another chip in the row above it. */
.djh-btn--primary {
  flex: 1 0 100%; justify-content: center; margin-top: 2px;
  color: #fff; background: var(--accent); font-weight: 600;
}
.djh-btn--primary:hover:not(:disabled) { background: #6b6be0; }
.djh-btn:disabled, .djh-icon:disabled { color: #5c5c64; background: rgba(255,255,255,.04); cursor: default; }
.djh-btn:focus-visible, .djh-icon:focus-visible, .djh-seg-btn:focus-visible, .djh-scrub:focus-visible {
  outline: 2px solid #a5b4fc; outline-offset: 2px;
}
@media (prefers-reduced-motion: no-preference) {
  .djh-btn, .djh-icon, .djh-seg-btn { transition: background 150ms ease-out, color 150ms ease-out; }
}

/* inline-flex centring, not line-height guesswork — a digit's box is not its ink, so
   text-align alone leaves the number sitting low in the circle. */
.djh-badge {
  display: inline-flex; align-items: center; justify-content: center;
  box-sizing: content-box;
  min-width: 10px; height: 16px; padding: 0 3px; border-radius: 999px;
  font-size: 10px; font-weight: 700; line-height: 1;
  font-variant-numeric: tabular-nums; letter-spacing: 0;
  color: #16161a; background: var(--txt);
}
.djh-btn--on .djh-badge, .djh-btn--primary .djh-badge { color: var(--accent); background: #fff; }
.djh-badge--fab {
  position: absolute; top: -2px; right: -2px;
  height: 18px; min-width: 12px;
  color: #fff; background: var(--accent);
  box-shadow: 0 0 0 2px #16161a;
}

.djh-scrub { flex: 1 1 110px; min-width: 60px; accent-color: var(--accent); }
.djh-note {
  margin: 0; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-size: 11px; color: var(--dim);
}
.djh-flash {
  margin: 0; padding: 0 14px 8px;
  font-size: 11px; color: #7ee2a8;
}
@media (max-width: 680px) {
  .djh-dock { right: 12px; left: 12px; width: auto; max-width: none; }
  .djh-stage--split { grid-template-columns: 1fr; }
  .djh-stage--split .djh-pane + .djh-pane { border-left: none; border-top: 1px solid rgba(128,128,128,.35); }
}
`;
