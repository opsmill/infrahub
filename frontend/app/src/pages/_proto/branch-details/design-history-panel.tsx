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

import { Annotations, type Note, notesToMarkdown } from "./design-annotations";

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
  revisions: Revision[];
};

type Props = {
  slug: string;
  variants: Variant[];
  /** Values worth tuning without an agent. Exposing one is a design decision — be sparing. */
  knobs?: Knob[];
  /** Fixed-position box the shell fills. Defaults to the whole viewport. */
  frame?: CSSProperties;
};

export function DesignHistory({ slug, variants, knobs = [], frame }: Props) {
  const params = new URLSearchParams(window.location.search);

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
      knobs.map((k) => {
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
  const [saved, setSaved] = useState("");

  const variant = (variants.find((v) => v.id === variantId) ?? variants[0]) as Variant;
  const latest = latestOf(variant);
  const current = (variant.revisions.find((r) => r.rev === rev) ??
    variant.revisions.at(-1)) as Revision;
  const other = compareWith ? (variant.revisions.find((r) => r.rev === compareWith) ?? null) : null;
  const stale = current.rev !== latest;
  const scope = `${slug}:${variant.id}:rev${current.rev}`;
  const written = notes.filter((n) => n.text.trim()).length;

  useEffect(() => {
    const next = new URLSearchParams(window.location.search);
    next.set("variant", variant.id);
    next.set("rev", String(current.rev));
    if (other) next.set("compare", String(other.rev));
    else next.delete("compare");
    for (const k of knobs) {
      const v = values[k.key];
      next.set(`k.${k.key}`, typeof v === "boolean" ? (v ? "1" : "0") : String(v));
    }
    window.history.replaceState(null, "", `?${next.toString()}`);
  }, [variant.id, current.rev, other, values, knobs]);

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
    const knobLines = knobs.map((k) => `- ${k.label} (\`${k.key}\`): ${values[k.key]}`).join("\n");
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
      if (res.ok) {
        flash(`✓ Sent — agent reads .design/${slug}/feedback.md`);
        return;
      }
    } catch {
      /* no dev server — fall through to the clipboard */
    }
    await copy();
  };

  const pane = (r: Revision, tag: string | null, annotate: boolean) => (
    <section className="djh-pane">
      {tag && <header className="djh-pane-tag">{tag}</header>}
      {annotate ? (
        <Annotations scope={scope} armed={armed} onArmedChange={setArmed} onNotesChange={setNotes}>
          {r.render(values)}
        </Annotations>
      ) : (
        r.render(values)
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

      {open && knobsOpen && knobs.length > 0 && (
        <div className="djh-knobs">
          {knobs.map((k) => (
            // biome-ignore lint/a11y/noLabelWithoutControl: every branch below renders the wrapped control
            <label key={k.key} className="djh-knob">
              <span>{k.label}</span>
              {k.type === "range" && (
                <>
                  <input
                    type="range"
                    min={k.min}
                    max={k.max}
                    step={k.step ?? 1}
                    value={Number(values[k.key])}
                    onChange={(e) => setValues({ ...values, [k.key]: Number(e.target.value) })}
                  />
                  <output>{String(values[k.key])}</output>
                </>
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
            onClick={() => setValues(Object.fromEntries(knobs.map((k) => [k.key, k.value])))}
          >
            Reset values
          </button>
        </div>
      )}

      <div className={open ? "djh-bar" : "djh-bar djh-bar--closed"}>
        {open ? (
          <>
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
                <span className="djh-note" title={current.date}>
                  {current.note}
                </span>
              </div>
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
                  {written === 0 ? "Send" : `Send ${written} ${written === 1 ? "note" : "notes"}`}
                </button>
              </div>
            </section>

            {saved && (
              <p className="djh-flash" role="status">
                {saved}
              </p>
            )}
          </>
        ) : (
          <button type="button" className="djh-btn" onClick={() => setOpen(true)}>
            {variant.label} · rev {current.rev}
            {written > 0 && <span className="djh-badge">{written}</span>}
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
.djh-knobs {
  flex: none;
  display: flex; flex-wrap: wrap; align-items: center; gap: 10px 20px;
  padding: 10px 12px;
  font: 500 12px/1.4 system-ui, sans-serif; color: #e4e4e7;
  background: #27272a; border-top: 1px solid rgba(255,255,255,.1);
}
.djh-knob { display: flex; align-items: center; gap: 8px; }
.djh-knob > span { color: #a1a1aa; }
.djh-knob output { min-width: 2.5ch; font-variant-numeric: tabular-nums; }
.djh-knob input[type="range"] { width: 120px; accent-color: #6366f1; }
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
  flex: none;
  display: flex; flex-wrap: wrap; align-items: stretch; gap: 0;
  padding: 0 4px;
  font: 500 12px/1.4 system-ui, sans-serif; color: var(--txt);
  background: #16161a; border-top: var(--hair) solid var(--line);
}
@media (min-resolution: 192dpi) { .djh-bar { --hair: 0.5px; } }
.djh-bar--closed { padding: 6px; justify-content: flex-end; }

.djh-zone {
  display: flex; flex-direction: column; justify-content: center; gap: 5px;
  min-width: 0; padding: 7px 14px;
}
.djh-zone + .djh-zone { border-left: var(--hair) solid var(--line); }
.djh-zone--grow { flex: 1 1 300px; }
/* The zone you act from sits fractionally above the rest of the bar. */
.djh-zone--act { background: rgba(255,255,255,.035); }
.djh-zone-label {
  display: flex; align-items: baseline; gap: 5px;
  font-size: 9px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase;
  color: var(--dim);
}
.djh-count { color: var(--txt); font-variant-numeric: tabular-nums; }
.djh-of { font-weight: 600; letter-spacing: .06em; }
.djh-row { display: flex; align-items: center; gap: 6px; min-width: 0; }

/* Segmented control: one object, so the directions read as alternatives, not as four
   unrelated buttons. Inner radius = outer (7) − padding (2). */
.djh-seg {
  display: flex; gap: 2px; padding: 2px; border-radius: 7px;
  background: rgba(255,255,255,.06);
}
.djh-seg-btn {
  font: inherit; cursor: pointer; white-space: nowrap;
  min-height: 24px; padding: 3px 10px; border-radius: 5px;
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
.djh-btn--primary { color: #fff; background: var(--accent); font-weight: 600; }
.djh-btn--primary:hover:not(:disabled) { background: #6b6be0; }
.djh-btn:disabled, .djh-icon:disabled { color: #5c5c64; background: rgba(255,255,255,.04); cursor: default; }
.djh-btn:focus-visible, .djh-icon:focus-visible, .djh-seg-btn:focus-visible, .djh-scrub:focus-visible {
  outline: 2px solid #a5b4fc; outline-offset: 2px;
}
@media (prefers-reduced-motion: no-preference) {
  .djh-btn, .djh-icon, .djh-seg-btn { transition: background 150ms ease-out, color 150ms ease-out; }
}

.djh-badge {
  min-width: 16px; padding: 0 4px; border-radius: 8px;
  font-size: 10px; font-weight: 700; text-align: center;
  font-variant-numeric: tabular-nums;
  color: #16161a; background: var(--txt);
}
.djh-btn--on .djh-badge, .djh-btn--primary .djh-badge { color: var(--accent); background: #fff; }

.djh-scrub { flex: 1 1 110px; min-width: 80px; accent-color: var(--accent); }
.djh-note {
  flex: 1 1 auto; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  color: var(--dim);
}
.djh-flash {
  flex: 1 0 100%; margin: 0; padding: 0 14px 7px;
  font-size: 11px; color: #7ee2a8;
}
@media (max-width: 860px) {
  .djh-zone + .djh-zone { border-left: none; border-top: var(--hair) solid var(--line); }
  .djh-zone { flex: 1 1 100%; }
}
@media (max-width: 680px) {
  .djh-stage--split { grid-template-columns: 1fr; }
  .djh-stage--split .djh-pane + .djh-pane { border-left: none; border-top: 1px solid rgba(128,128,128,.35); }
}
`;
