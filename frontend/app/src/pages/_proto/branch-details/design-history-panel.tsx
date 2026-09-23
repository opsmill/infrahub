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
    setTimeout(() => setSaved(""), 1800);
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(asMarkdown());
      flash("Copied");
    } catch {
      flash("Copy blocked");
    }
  };

  const save = async () => {
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
      flash(res.ok ? "Saved to .design/" : "Save failed — use Copy");
    } catch {
      flash("No dev server — use Copy");
    }
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
            className="djh-tab"
            onClick={() => setValues(Object.fromEntries(knobs.map((k) => [k.key, k.value])))}
          >
            Reset
          </button>
        </div>
      )}

      <div className={open ? "djh-bar" : "djh-bar djh-bar--closed"}>
        {open ? (
          <>
            <div className="djh-group">
              <span className="djh-key">{slug}</span>
              {variants.map((v) => (
                <button
                  key={v.id}
                  type="button"
                  title={v.bet}
                  className={v.id === variant.id ? "djh-tab djh-tab--on" : "djh-tab"}
                  onClick={() => pickVariant(v.id)}
                >
                  {v.label}
                </button>
              ))}
            </div>

            <div className="djh-group djh-group--grow">
              <button
                type="button"
                className="djh-step"
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
                className="djh-step"
                aria-label="Next revision"
                disabled={current.rev >= latest}
                onClick={() => setRev(current.rev + 1)}
              >
                ›
              </button>
              <span className="djh-note" title={current.date}>
                <b>rev {current.rev}</b> {current.note}
              </span>
            </div>

            <div className="djh-group">
              {knobs.length > 0 && (
                <button
                  type="button"
                  className={knobsOpen ? "djh-tab djh-tab--on" : "djh-tab"}
                  onClick={() => setKnobsOpen(!knobsOpen)}
                >
                  Knobs
                </button>
              )}
              <button
                type="button"
                className={armed ? "djh-tab djh-tab--rec" : "djh-tab"}
                onClick={() => setArmed(!armed)}
              >
                {armed ? "Click a spot…" : `Note${written ? ` (${written})` : ""}`}
              </button>
              <button type="button" className="djh-tab" onClick={copy}>
                Copy
              </button>
              <button type="button" className="djh-tab" onClick={save}>
                Save
              </button>
              <button
                type="button"
                className={other ? "djh-tab djh-tab--on" : "djh-tab"}
                onClick={() => setCompareWith(other ? null : latest)}
              >
                Compare
              </button>
              <button
                type="button"
                className="djh-tab"
                disabled={!stale}
                onClick={() => setRev(latest)}
              >
                Latest
              </button>
              <button type="button" className="djh-tab" onClick={() => setOpen(false)}>
                Hide
              </button>
              {saved && <span className="djh-flash">{saved}</span>}
            </div>
          </>
        ) : (
          <button type="button" className="djh-tab" onClick={() => setOpen(true)}>
            {variant.label} · rev {current.rev}
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
.djh-bar {
  flex: none;
  display: flex; flex-wrap: wrap; align-items: center; gap: 8px 16px;
  padding: 8px 12px;
  font: 500 12px/1.4 system-ui, sans-serif; color: #f4f4f5;
  background: #18181b; border-top: 1px solid rgba(255,255,255,.12);
}
.djh-bar--closed { justify-content: flex-end; padding: 4px 8px; }
.djh-group { display: flex; align-items: center; gap: 8px; min-width: 0; }
.djh-group--grow { flex: 1 1 320px; }
.djh-key {
  font: 500 11px/1 ui-monospace, monospace; letter-spacing: .06em;
  color: #a1a1aa; padding-right: 4px;
}
.djh-tab, .djh-step {
  font: inherit; cursor: pointer; white-space: nowrap;
  padding: 4px 10px; border-radius: 6px;
  color: #e4e4e7; background: rgba(255,255,255,.07);
  border: 1px solid transparent;
}
.djh-step { padding: 2px 9px; font-size: 15px; line-height: 1.2; }
.djh-tab:hover, .djh-step:hover:not(:disabled) { background: rgba(255,255,255,.16); }
.djh-tab--on { background: #4f46e5; border-color: #6366f1; color: #fff; }
.djh-tab--rec { background: #b91c1c; border-color: #ef4444; color: #fff; }
.djh-tab:disabled, .djh-step:disabled { opacity: .35; cursor: default; }
.djh-tab:focus-visible, .djh-step:focus-visible, .djh-scrub:focus-visible {
  outline: 2px solid #a5b4fc; outline-offset: 2px;
}
.djh-scrub { flex: 1 1 120px; min-width: 90px; accent-color: #6366f1; }
.djh-note {
  flex: 1 1 auto; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  color: #a1a1aa;
}
.djh-note b { color: #f4f4f5; font-weight: 600; }
.djh-flash { color: #86efac; }
@media (max-width: 680px) {
  .djh-stage--split { grid-template-columns: 1fr; }
  .djh-stage--split .djh-pane + .djh-pane { border-left: none; border-top: 1px solid rgba(128,128,128,.35); }
}
`;
