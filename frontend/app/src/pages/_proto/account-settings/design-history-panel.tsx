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
 */

import {
  type CSSProperties,
  type ReactNode,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

import { Annotations, notesToMarkdown } from "./design-annotations";
import { type Note, readReviewerName, useNotesStore, writeReviewerName } from "./notes-store";

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

/**
 * Every query param this panel owns is namespaced, because the prototype route lives in
 * the real app and shares its URL: a bare `variant` or `compare` is exactly the kind of
 * name a page already uses, and the collision is silent in both directions — the app
 * reads our value, or we clobber theirs. Params outside this namespace are preserved
 * untouched on every write.
 */
const NS = "dj";
const q = (key: string) => `${NS}.${key}`;

/** "updated 12s ago" — coarse on purpose; it says "not live", not "how not live". */
const ago = (t?: number) => {
  if (!t) return "—";
  const s = Math.max(0, Math.round((Date.now() - t) / 1000));
  return s < 60 ? `${s}s ago` : `${Math.round(s / 60)}m ago`;
};

type Props = {
  slug: string;
  variants: Variant[];
  /** Knobs that apply to every direction. Exposing one is a design decision — be sparing. */
  knobs?: Knob[];
  /**
   * Fixed-position box the shell fills; defaults to the whole viewport. Pass the app's
   * content area so the real sidebar and top bar stay on screen — a screen reviewed
   * without its surrounding chrome is reviewed at a width it will never have.
   */
  frame?: CSSProperties;
  /**
   * The draft design PR. When set, the primary action is *Post to PR*: reviewers' notes
   * reach the owner as a PR comment, because the preview is used through one shared login
   * and nothing on the instance can say who wrote what.
   */
  prUrl?: string;
};

export function DesignHistory({ slug, variants, knobs: shared = [], frame, prUrl }: Props) {
  const params = new URLSearchParams(window.location.search);

  /** Every knob any direction could show — so switching never lands on an undefined value. */
  const allKnobs = [...shared, ...variants.flatMap((v) => v.knobs ?? [])];

  // The casts and `.at(-1)` guards are for `noUncheckedIndexedAccess`, which this repo
  // enables — plain `variants[0]` does not typecheck here.
  const initialVariant = (variants.find((v) => v.id === params.get(q("variant"))) ??
    variants[0]) as Variant;
  const latestOf = (v: Variant) => v.revisions.at(-1)?.rev ?? 1;

  const [variantId, setVariantId] = useState(initialVariant.id);
  const [rev, setRev] = useState(() => {
    const asked = Number(params.get(q("rev")));
    return Number.isFinite(asked) && asked > 0 ? asked : latestOf(initialVariant);
  });
  const [compareWith, setCompareWith] = useState<number | null>(() => {
    const asked = Number(params.get(q("compare")));
    return Number.isFinite(asked) && asked > 0 ? asked : null;
  });
  const [values, setValues] = useState<Record<string, KnobValue>>(() =>
    Object.fromEntries(
      allKnobs.map((k) => {
        const raw = params.get(q(`k.${k.key}`));
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
  const [saved, setSaved] = useState("");
  const [allCount, setAllCount] = useState(0);
  /** Owner-only feedback tools, tucked behind ⋯ so a reviewer sees two buttons, not three. */
  const [more, setMore] = useState(false);
  const [reviewer, setReviewer] = useState(readReviewerName);
  const [editingName, setEditingName] = useState(false);

  /**
   * The dock snaps to a corner rather than sitting anywhere: a free-floating panel ends
   * up half off-screen or over the one thing you wanted to see, and "which corner" is a
   * single value that survives a reload. Per-viewer, so localStorage is the right home.
   */
  type Corner = "br" | "bl" | "tr" | "tl";
  const [corner, setCorner] = useState<Corner>(() => {
    try {
      const saved = localStorage.getItem("design-jam:corner");
      return saved === "bl" || saved === "tr" || saved === "tl" ? saved : "br";
    } catch {
      return "br";
    }
  });
  /**
   * Only "is a drag happening" lives in React state. The position does not: a state update
   * per pointermove re-renders the whole panel — zones, knobs, the note list — for every
   * event, and pointer events arrive faster than that render can finish, which is the
   * low-fps feel. The transform is written straight to the DOM instead, coalesced to one
   * write per frame with requestAnimationFrame.
   */
  const [dragging, setDragging] = useState(false);
  const movedRef = useRef(false);
  const dockRef = useRef<HTMLDivElement>(null);
  const pendingRef = useRef<{ dx: number; dy: number } | null>(null);
  const rafRef = useRef<number>(0);
  /** Where the dock visually was at release, so the settle can start from the hand. */
  const settleFrom = useRef<{ left: number; top: number } | null>(null);
  const [settleTick, setSettleTick] = useState(0);

  /**
   * The settle is a FLIP: React has already moved the dock to its new corner (an instant
   * change of fixed offsets — never animated, those are layout properties), so we measure
   * where it landed, translate it back to where the hand let go, then transition that
   * translate to zero. Transform only, so it runs on the compositor; a strong ease-out so
   * it leaves the hand fast and brakes into the corner; duration scaled to the distance,
   * capped where UI motion stops feeling fast. Interruptible: grabbing mid-settle sets an
   * inline transform with the transition off, and the browser retargets from wherever
   * the dock currently is instead of restarting.
   */
  useLayoutEffect(() => {
    const el = dockRef.current;
    const from = settleFrom.current;
    settleFrom.current = null;
    if (!el || !from) return;
    // The drag's inline transform is still on the element. Clear it first — before the
    // reduced-motion return, or a reduced-motion user is left with the dock stuck where
    // they dropped it — so `to` is the true resting position in the new corner.
    el.style.transform = "";
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const to = el.getBoundingClientRect();
    const dx = from.left - to.left;
    const dy = from.top - to.top;
    if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return;

    el.style.transition = "none";
    el.style.transform = `translate(${dx}px, ${dy}px) scale(1.02)`;
    const ms = Math.round(Math.min(320, Math.max(180, Math.hypot(dx, dy) * 0.22)));
    const raf = requestAnimationFrame(() => {
      el.style.transition = `transform ${ms}ms cubic-bezier(0.32, 0.72, 0, 1)`;
      el.style.transform = "";
    });
    const done = () => {
      el.style.transition = "";
      el.removeEventListener("transitionend", done);
    };
    el.addEventListener("transitionend", done);
    return () => cancelAnimationFrame(raf);
  }, [settleTick]);

  useEffect(() => {
    try {
      localStorage.setItem("design-jam:corner", corner);
    } catch {
      /* fine — it just won't remember the corner */
    }
  }, [corner]);

  const onGrip = (e: React.PointerEvent<HTMLElement>) => {
    if (e.button !== 0) return;
    const start = { x: e.clientX, y: e.clientY };
    movedRef.current = false;
    e.currentTarget.setPointerCapture(e.pointerId);
    // Grabbing mid-settle: drop the settle's inline transition so the drag follows the
    // hand 1:1 from wherever the dock is right now.
    if (dockRef.current) dockRef.current.style.transition = "none";
    const move = (ev: PointerEvent) => {
      const dx = ev.clientX - start.x;
      const dy = ev.clientY - start.y;
      if (!movedRef.current) {
        if (Math.abs(dx) <= 4 && Math.abs(dy) <= 4) return;
        movedRef.current = true;
        setDragging(true); // one render, at the threshold, not one per event
      }
      pendingRef.current = { dx, dy };
      if (rafRef.current) return; // a write is already scheduled for this frame
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = 0;
        const p = pendingRef.current;
        const el = dockRef.current;
        if (p && el) el.style.transform = `translate(${p.dx}px, ${p.dy}px) scale(1.02)`;
      });
    };
    const up = (ev: PointerEvent) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = 0;
      }
      if (!movedRef.current) return;
      // Flush the last pending position so the measurement below is exactly where the
      // hand let go — the rect includes the inline drag translate.
      const p = pendingRef.current;
      const el = dockRef.current;
      if (p && el) el.style.transform = `translate(${p.dx}px, ${p.dy}px) scale(1.02)`;
      const r = el?.getBoundingClientRect();
      if (r) settleFrom.current = { left: r.left, top: r.top };
      const right = ev.clientX > window.innerWidth / 2;
      const bottom = ev.clientY > window.innerHeight / 2;
      setDragging(false);
      setCorner(`${bottom ? "b" : "t"}${right ? "r" : "l"}` as Corner);
      setSettleTick((t) => t + 1);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
  };

  /** Keyboard path for the same thing: pressing the grip walks the corners clockwise. */
  const cycleCorner = () => {
    if (movedRef.current) return;
    const order: Corner[] = ["br", "bl", "tl", "tr"];
    setCorner(order[(order.indexOf(corner) + 1) % order.length] as Corner);
  };

  const variant = (variants.find((v) => v.id === variantId) ?? variants[0]) as Variant;
  const latest = latestOf(variant);
  const current =
    variant.revisions.find((r) => r.rev === rev) ?? (variant.revisions.at(-1) as Revision);
  const other = compareWith ? (variant.revisions.find((r) => r.rev === compareWith) ?? null) : null;
  const stale = current.rev !== latest;
  const scope = `${slug}:${variant.id}:rev${current.rev}`;

  // Local by default; switches to the Infrahub instance when the DesignJamNote kind is
  // loaded there. Polls while visible, refetches on focus and after our own writes.
  const store = useNotesStore(slug, scope);
  const notes = store.notes;
  useEffect(() => {
    store
      .all()
      .then((groups) => setAllCount(Object.values(groups).reduce((n, ns) => n + ns.length, 0)));
  }, [store.all, notes.length]);

  /**
   * Embed mode: this document is one side of a comparison, loaded in an iframe by the
   * parent. It renders the design and nothing else — no dock, no alert, no pin tool — so
   * the two sides show exactly the app and only the app.
   */
  const embed = params.get(q("embed")) === "1";

  /** The URL for one side of a comparison: same variant and knobs, a fixed rev, embed on. */
  const sideUrl = (r: number) => {
    const u = new URL(window.location.href);
    u.searchParams.set(q("embed"), "1");
    u.searchParams.set(q("rev"), String(r));
    u.searchParams.delete(q("compare"));
    return u.toString();
  };

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
  const activeValues = Object.fromEntries(knobs.map((k) => [k.key, values[k.key]])) as Record<
    string,
    KnobValue
  >;
  const written = notes.filter((n) => n.text.trim() && !n.sentAt).length;

  useEffect(() => {
    // Starts from the live search string, so the app's own params survive every write.
    const next = new URLSearchParams(window.location.search);
    next.set(q("variant"), variant.id);
    next.set(q("rev"), String(current.rev));
    if (other) next.set(q("compare"), String(other.rev));
    else next.delete(q("compare"));
    // Only the active knobs go in the URL; a link never carries a control the recipient
    // won't see on the direction it opens.
    for (const k of allKnobs) next.delete(q(`k.${k.key}`));
    for (const k of knobs) {
      const v = values[k.key];
      next.set(q(`k.${k.key}`), typeof v === "boolean" ? (v ? "1" : "0") : String(v));
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

  const knobLines = () =>
    knobs
      .map(
        (k) =>
          `- ${k.label} (\`${k.key}\`): ${values[k.key]}${
            ownKeys.has(k.key) ? ` — ${variant.label} only` : ""
          }`
      )
      .join("\n");

  /** This revision only — what Copy rev puts on the clipboard. */
  const asMarkdown = () =>
    [
      `## design-jam feedback — ${slug} · ${variant.label} · rev ${current.rev}`,
      // The link is what makes a pasted note actionable by someone else: it reopens the
      // exact direction, revision and knob values the note was written against.
      `\n${window.location.href}`,
      knobs.length ? `\n### Knobs\n${knobLines()}` : "",
      `\n### Notes\n${notesToMarkdown(notes) || "_No notes._"}`,
    ].join("\n");

  /**
   * Every note on the whole run, grouped by direction and revision, each group with the
   * link that reopens it. This is the owner's gather step: paste it into `/design-jam`
   * locally and triage. Includes the live scope's unsaved state so nothing is missed.
   */
  const allAsMarkdown = async ({ unsentOnly = false } = {}) => {
    const keep = (ns: Note[]) => ns.filter((n) => n.text.trim() && !(unsentOnly && n.sentAt));
    const groups = Object.fromEntries(
      Object.entries({ ...(await store.all()), [scope]: notes }).map(([sc, ns]) => [sc, keep(ns)])
    );
    const sections = Object.entries(groups)
      .filter(([, ns]) => ns.length)
      .sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true }))
      .map(([sc, ns]) => {
        const [, vId, revPart] = sc.split(":");
        const r = Number((revPart ?? "").replace("rev", ""));
        const v = variants.find((x) => x.id === vId);
        const u = new URL(window.location.href);
        u.searchParams.set(q("variant"), vId ?? variant.id);
        u.searchParams.set(q("rev"), String(r));
        u.searchParams.delete(q("compare"));
        u.searchParams.delete(q("embed"));
        const open = ns.filter((n) => !n.status || n.status === "open").length;
        return [
          `### ${v?.label ?? vId} · rev ${r} — ${ns.length} note${ns.length === 1 ? "" : "s"}, ${open} open`,
          u.toString(),
          "",
          notesToMarkdown(ns),
        ].join("\n");
      });
    if (!sections.length) return "";
    return [
      // The marker is how the agent finds these among ordinary PR comments when it gathers.
      `<!-- design-jam:${slug} -->`,
      `## design-jam feedback — ${slug}${reviewer ? ` — from ${reviewer}` : ""}`,
      knobs.length
        ? `\n### Current knobs (${variant.label} · rev ${current.rev})\n${knobLines()}`
        : "",
      "",
      sections.join("\n\n"),
    ].join("\n");
  };
  const totalNotes = allCount;

  const flash = (msg: string) => {
    setSaved(msg);
    setTimeout(() => setSaved(""), 2600);
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(asMarkdown());
      flash("✓ Copied this revision's notes");
    } catch {
      flash("Clipboard blocked by the browser");
    }
  };

  const copyAll = async () => {
    try {
      await navigator.clipboard.writeText((await allAsMarkdown()) || "_No notes yet._");
      flash("✓ Copied every note on this run — paste it into /design-jam");
    } catch {
      flash("Clipboard blocked by the browser");
    }
  };

  const saveName = (name: string) => {
    writeReviewerName(name);
    setReviewer(name.trim());
    setEditingName(false);
  };

  /**
   * Copies this reviewer's new notes and opens the PR's comment box. GitHub cannot
   * pre-fill a comment from a link, so the paste is the one manual step. Posted notes are
   * marked, so the next post carries only what was added since.
   */
  const postToPr = async () => {
    if (!prUrl) return;
    if (!reviewer) {
      setEditingName(true);
      flash("Add your name first, so the owner knows who wrote these");
      return;
    }
    const md = await allAsMarkdown({ unsentOnly: true });
    if (!md) {
      flash("No new notes since your last post");
      return;
    }
    try {
      await navigator.clipboard.writeText(md);
    } catch {
      flash("Clipboard blocked by the browser");
      return;
    }
    window.open(`${prUrl}#new_comment_field`, "_blank", "noopener");
    store.markAllSent();
    flash("✓ Copied — paste it into the comment box on the PR");
  };

  /**
   * One side of a comparison: a label and a full copy of the app in an iframe. Two panes
   * inside the content area could only ever compare the content area; a change to the
   * sidebar, header, or anything outside the route would be invisible. Two documents
   * compare everything.
   */
  const side = (r: Revision, role: "primary" | "reference") => (
    <figure className={role === "reference" ? "djh-side djh-side--ref" : "djh-side"}>
      <figcaption className="djh-pane-tag">
        <span className="djh-pane-rev">rev {r.rev}</span>
        {r.rev === latest ? (
          <span className="djh-pane-chip">latest</span>
        ) : (
          <span className="djh-pane-chip djh-pane-chip--stale">not latest</span>
        )}
        <span className="djh-pane-note" title={r.note}>
          {r.note}
        </span>
        <span className="djh-pane-role">{role === "primary" ? "current" : "compared"}</span>
      </figcaption>
      <iframe
        className="djh-side-frame"
        title={`${variant.label} — revision ${r.rev}`}
        src={sideUrl(r.rev)}
      />
    </figure>
  );

  if (embed) {
    return (
      <div className="djh-root" style={frame}>
        <style>{css}</style>
        <div className="djh-stage">
          <section className="djh-pane">{current.render(activeValues)}</section>
        </div>
      </div>
    );
  }

  return (
    <>
      <style>{css}</style>

      {/*
        Fixed to the viewport, not to `frame`: the warning outranks the design being
        reviewed, so it has to clear the app's own sidebar and top bar. The layer is inert
        and only the pill takes clicks, so nothing behind it becomes unreachable.
      */}
      {/* Not in compare mode: there the side headers already name each revision, and
          looking at an old one is the point. The stale chip moves into the header. */}
      {stale && !other && (
        <div className="djh-alert-layer">
          <div className="djh-alert" role="status">
            <svg viewBox="0 0 24 24" aria-hidden="true" width="16" height="16">
              <g fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round">
                <path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1" />
                <path d="M3 4v4h4" strokeLinejoin="round" />
                <path d="M12 8v4.4l2.8 1.7" />
              </g>
            </svg>
            <span className="djh-alert-text">
              Revision <b>{current.rev}</b> of <b>{latest}</b> — not the latest
            </span>
            <button type="button" className="djh-alert-btn" onClick={() => setRev(latest)}>
              Go to latest
            </button>
          </div>
        </div>
      )}

      {/*
      Compare mode ignores `frame` on purpose and takes the whole viewport: each side is a
      complete app, so the split is the only chrome that should be visible.
    */}
      {other && (
        <div className="djh-split">
          {side(current, "primary")}
          {side(other, "reference")}
        </div>
      )}

      <div className="djh-root" style={frame} hidden={Boolean(other)}>
        <div className="djh-stage">
          <section className="djh-pane">
            <Annotations
              scope={scope}
              notes={notes}
              isMine={store.isMine}
              onAdd={store.add}
              onUpdate={store.update}
              onRemove={store.remove}
              armed={armed}
              onArmedChange={setArmed}
            >
              {current.render(activeValues)}
            </Annotations>
          </section>
        </div>
      </div>

      {/* Fixed to the viewport, a sibling of both the shell and the split, so the controls
          survive switching between single and compare views. */}
      {/* No `style` prop: the drag writes `transform` to this element directly, and React
          must not own that attribute or it would overwrite the value on every render. */}
      <div
        ref={dockRef}
        className={`djh-dock djh-dock--${corner}${dragging ? "djh-dock--dragging" : ""}`}
      >
        {open && knobsOpen && knobs.length > 0 && (
          <div className="djh-knobs">
            {knobs.map((k, i) => (
              // biome-ignore lint/a11y/noLabelWithoutControl: the control is rendered inside, per knob type
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
            {/* Header: what run this is, and the two things that act on the panel itself
                (move, hide). Panel-level actions live here, never inside a section, so a
                section's buttons are always about that section's subject. */}
            <header className="djh-head">
              <button
                type="button"
                className="djh-grip"
                aria-label="Move panel to another corner — drag it, or press to cycle"
                title="Drag to another corner"
                onPointerDown={onGrip}
                onClick={cycleCorner}
              >
                <svg viewBox="0 0 6 20" width="6" height="20" aria-hidden="true">
                  <g fill="currentColor">
                    <circle cx="3" cy="3" r="1.4" />
                    <circle cx="3" cy="10" r="1.4" />
                    <circle cx="3" cy="17" r="1.4" />
                  </g>
                </svg>
              </button>
              <span className="djh-title" title={slug}>
                {slug}
              </span>
              <button
                type="button"
                className="djh-icon"
                aria-label="Hide panel (H)"
                title="Hide (H)"
                onClick={() => setOpen(false)}
              >
                ×
              </button>
            </header>

            <section className="djh-zone">
              <div className="djh-zone-head">
                <span className="djh-zone-label">Prototype</span>
                {knobs.length > 0 && (
                  <button
                    type="button"
                    aria-pressed={knobsOpen}
                    className={
                      knobsOpen ? "djh-btn djh-btn--sm djh-btn--on" : "djh-btn djh-btn--sm"
                    }
                    title="Tune this prototype's exposed values (K)"
                    onClick={() => setKnobsOpen(!knobsOpen)}
                  >
                    Knobs
                  </button>
                )}
              </div>
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
              <div className="djh-zone-head">
                <span className="djh-zone-label">
                  Revision <b className="djh-count">{current.rev}</b>
                  <span className="djh-of">of {latest}</span>
                </span>
                <div className="djh-row djh-row--tight">
                  {stale && (
                    <button
                      type="button"
                      className="djh-btn djh-btn--sm"
                      title="Jump to the latest revision (L)"
                      onClick={() => setRev(latest)}
                    >
                      Latest
                    </button>
                  )}
                  <button
                    type="button"
                    aria-pressed={Boolean(other)}
                    className={other ? "djh-btn djh-btn--sm djh-btn--on" : "djh-btn djh-btn--sm"}
                    title="Compare two revisions as two full apps (C)"
                    onClick={() => setCompareWith(other ? null : latest)}
                  >
                    Compare
                  </button>
                </div>
              </div>
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
              {other ? (
                <div className="djh-row">
                  <span className="djh-vs">compared with</span>
                  <select
                    className="djh-select"
                    aria-label="Revision to compare against"
                    value={other.rev}
                    onChange={(e) => setCompareWith(Number(e.target.value))}
                  >
                    {variant.revisions.map((r) => (
                      <option key={r.rev} value={r.rev} disabled={r.rev === current.rev}>
                        rev {r.rev}
                        {r.rev === latest ? " (latest)" : ""}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="djh-icon"
                    aria-label="Swap the two sides"
                    title="Swap sides"
                    onClick={() => {
                      const a = current.rev;
                      setRev(other.rev);
                      setCompareWith(a);
                    }}
                  >
                    ⇄
                  </button>
                </div>
              ) : (
                <p className="djh-note" title={current.date}>
                  {current.note}
                </p>
              )}
            </section>

            <section className="djh-zone djh-zone--act">
              <div className="djh-zone-head">
                <span className="djh-zone-label">Feedback</span>
                <button
                  type="button"
                  aria-pressed={more}
                  aria-label="Owner tools"
                  title="Owner tools: copy every note, or this revision only"
                  className={more ? "djh-btn djh-btn--sm djh-btn--on" : "djh-btn djh-btn--sm"}
                  onClick={() => setMore(!more)}
                >
                  ⋯
                </button>
              </div>

              {/* Where the notes live, in plain words, on its own line — not crammed into
                  the section label. A poll is stated as a poll. */}
              <p className="djh-status">
                {store.backend === "infrahub" ? (
                  <>
                    <span className="djh-status-dot djh-status-dot--on" aria-hidden="true" />
                    Shared on this instance ·{" "}
                    <span className="djh-count">
                      {store.isFetching ? "refreshing…" : `updated ${ago(store.updatedAt)}`}
                    </span>
                    <button
                      type="button"
                      className="djh-fresh-btn"
                      onClick={() => store.refresh()}
                      aria-label="Refresh notes now"
                      title="Refresh now (polls every 15s)"
                    >
                      ↻
                    </button>
                  </>
                ) : (
                  <>
                    <span className="djh-status-dot" aria-hidden="true" />
                    {prUrl ? "In this browser until you post" : "This browser only"}
                    {" · "}
                    {editingName || !reviewer ? (
                      <input
                        className="djh-name"
                        aria-label="Your name"
                        placeholder="your name"
                        defaultValue={reviewer}
                        autoFocus={editingName}
                        onBlur={(e) => saveName(e.currentTarget.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") saveName(e.currentTarget.value);
                        }}
                      />
                    ) : (
                      <button
                        type="button"
                        className="djh-fresh-btn djh-fresh-btn--text"
                        title="Change your name"
                        onClick={() => setEditingName(true)}
                      >
                        as {reviewer}
                      </button>
                    )}
                    {store.canEnable && (
                      <>
                        {" · "}
                        <button
                          type="button"
                          className="djh-fresh-btn djh-fresh-btn--text"
                          title="Load the DesignJamNote schema on this instance so every reviewer sees every pin (admin, once, preview only)"
                          onClick={() =>
                            store.enable().then(
                              () => flash("✓ Shared notes enabled on this instance"),
                              () =>
                                flash(
                                  "Could not load the schema — admin only, preview instances only"
                                )
                            )
                          }
                        >
                          enable shared
                        </button>
                      </>
                    )}
                  </>
                )}
              </p>

              <div className="djh-row">
                <button
                  type="button"
                  aria-pressed={armed}
                  className={armed ? "djh-btn djh-btn--on" : "djh-btn"}
                  title="Pin a note on the design (A)"
                  onClick={() => setArmed(!armed)}
                >
                  {armed ? "Click the spot…" : "Add note"}
                  {!armed && written > 0 && <span className="djh-badge">{written}</span>}
                </button>
                {/* The one primary action. On a preview: post to the design PR, which is
                    where the owner gathers from. Without a PR yet: copy, and paste into
                    /design-jam. */}
                {prUrl ? (
                  <button
                    type="button"
                    className="djh-btn djh-btn--primary"
                    disabled={totalNotes === 0 && written === 0}
                    title="Copy your new notes and open the PR to paste them"
                    onClick={postToPr}
                  >
                    Post to PR
                    {written > 0 && <span className="djh-badge">{written}</span>}
                  </button>
                ) : (
                  <button
                    type="button"
                    className="djh-btn djh-btn--primary"
                    disabled={totalNotes === 0 && written === 0}
                    onClick={copyAll}
                  >
                    Copy all notes
                    {totalNotes > 0 && <span className="djh-badge">{totalNotes}</span>}
                  </button>
                )}
              </div>

              {more && (
                <div className="djh-row djh-row--more">
                  <span className="djh-more-label">Owner</span>
                  {prUrl && (
                    <button
                      type="button"
                      className="djh-btn djh-btn--sm"
                      title="Copy every note on the run, posted or not"
                      onClick={copyAll}
                    >
                      Copy all
                    </button>
                  )}
                  <button
                    type="button"
                    className="djh-btn djh-btn--sm"
                    title="Copy this revision's notes only"
                    onClick={copy}
                  >
                    Copy rev
                  </button>
                </div>
              )}
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
            aria-label={`Show design panel — ${variant.label}, revision ${current.rev}. Drag to move.`}
            onPointerDown={onGrip}
            onClick={() => {
              if (!movedRef.current) setOpen(true);
            }}
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
    </>
  );
}

const css = `
/*
 * The panel owns the viewport: one fixed shell, the design scrolls inside it, the bar is a
 * sibling rather than an overlay. A fixed bar floating over a normally-scrolling page is
 * what produces dead space under the design and a page that scrolls out from under the
 * controls — this structure makes both impossible.
 */
/* A named scale, so nothing here ever reaches for z-index: 9999. */
:root {
  --djh-z-shell: 10;
  --djh-z-annotate: 40;
  --djh-z-dock: 50;
  --djh-z-alert: 400;
}
.djh-root {
  position: fixed; inset: 0; z-index: var(--djh-z-shell);
  display: flex; flex-direction: column;
  padding-bottom: env(safe-area-inset-bottom, 0px);
  background: Canvas;
}
/*
 * A pill centred at the top of the viewport rather than a full-width bar: it has to be
 * seen without covering the app chrome it floats over, and a bar that spans the window
 * reads as part of the product rather than as a warning about the thing being reviewed.
 * Amber, an icon and the words all say the same thing — colour alone is invisible to some
 * readers and easy to ignore for everyone else.
 */
.djh-alert-layer {
  position: fixed; top: 0; left: 0; right: 0; z-index: var(--djh-z-alert);
  display: flex; justify-content: center;
  padding: calc(12px + env(safe-area-inset-top, 0px)) 16px 0;
  pointer-events: none;
}
.djh-alert {
  display: flex; align-items: center; gap: 10px;
  max-width: 100%; padding: 7px 8px 7px 14px; border-radius: 999px;
  font: 500 13px/1.4 system-ui, sans-serif;
  color: #7c2d12; background: #ffedd5;
  box-shadow: 0 0 0 1px rgba(124,45,18,.18), 0 8px 24px -6px rgba(67,20,7,.35);
  pointer-events: auto;
}
.djh-alert svg { flex: none; color: #b45309; }
.djh-alert-text { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.djh-alert-text b { font-weight: 600; font-variant-numeric: tabular-nums; }
.djh-alert-btn {
  flex: none; position: relative;
  font: 600 13px/1 system-ui, sans-serif; cursor: pointer;
  padding: 7px 12px; border-radius: 999px;
  color: #fff; background: #9a3412; border: none;
}
/* 40px desktop hit area on a 30px pill, without changing how it looks. */
.djh-alert-btn::before { content: ""; position: absolute; inset: -5px; }
.djh-alert-btn:hover { background: #7c2d12; }
.djh-alert-btn:active { transform: scale(0.96); }
.djh-alert-btn:focus-visible { outline: 2px solid #431407; outline-offset: 2px; }
@media (prefers-reduced-motion: no-preference) {
  .djh-alert { animation: djh-drop 220ms ease-out both; }
  .djh-alert-btn { transition: background-color 150ms ease-out, transform 150ms ease-out; }
}
@keyframes djh-drop {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: none; }
}
.djh-stage {
  flex: 1 1 auto; min-height: 0;
  display: grid; grid-template-columns: 1fr;
}
.djh-pane {
  min-width: 0; min-height: 0;
  overflow: auto; overscroll-behavior: contain;
}

/* Compare: two complete apps, edge to edge, above the shell it replaces. */
.djh-split {
  position: fixed; inset: 0; z-index: var(--djh-z-shell);
  display: grid; grid-template-columns: 1fr 1fr;
  background: #0f0f12;
}
.djh-side {
  display: flex; flex-direction: column; margin: 0; min-width: 0;
}
.djh-side + .djh-side { border-left: 2px solid #0f0f12; }
.djh-side-frame {
  flex: 1 1 auto; width: 100%; min-height: 0; border: 0; background: Canvas;
}
/* Two near-identical screens side by side are unreadable without a label on each: which
   revision, whether it is the latest, and which one takes the notes. */
.djh-pane-tag {
  position: sticky; top: 0; z-index: 30;
  display: flex; align-items: center; gap: 8px;
  padding: 5px 12px;
  font: 600 11px/1.4 system-ui, sans-serif;
  color: #fff; background: #3730a3;
}
.djh-side--ref .djh-pane-tag { background: #3f3f46; }
.djh-pane-rev { font-variant-numeric: tabular-nums; letter-spacing: .04em; }
.djh-pane-chip {
  padding: 1px 6px; border-radius: 999px;
  font-size: 9px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase;
  color: #1e1b4b; background: #c7d2fe;
}
.djh-side--ref .djh-pane-chip { color: #27272a; background: #d4d4d8; }
/* Same amber as the single-view pill, so "not latest" means one thing everywhere. */
.djh-pane-chip--stale, .djh-side--ref .djh-pane-chip--stale { color: #7c2d12; background: #fed7aa; }
.djh-pane-tag { position: static; flex: none; }
.djh-pane-note {
  flex: 1 1 auto; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-weight: 400; opacity: .78;
}
.djh-pane-role {
  flex: none;
  font-size: 9px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase;
  opacity: .7;
}
.djh-vs { color: var(--dim); }
.djh-select {
  font: inherit; cursor: pointer;
  min-height: 26px; padding: 3px 8px; border-radius: 6px;
  color: var(--txt); background: rgba(255,255,255,.07); border: none;
}
.djh-select:focus-visible { outline: 2px solid #fff; outline-offset: 2px; }
/*
 * The tools float over the design rather than sitting in its layout: the design is the
 * thing being judged, so it gets the whole frame, and the panel is visibly an instrument
 * laid on top of it. The dock itself is click-through; only the panels inside it aren't.
 */
/* Anchored bottom-right at a fixed width, sections stacked. A full-width bar spanning the
   viewport competes with the design for the eye; a corner panel is read as a tool. */
.djh-dock {
  position: fixed; z-index: var(--djh-z-dock);
  width: 304px; max-width: calc(100% - 32px);
  display: flex; flex-direction: column; align-items: stretch; gap: 8px;
  pointer-events: none;
}
.djh-dock > * { pointer-events: auto; }
/* Four corners, one class each. Top corners flip the column so the knobs drawer opens
   toward the middle of the screen, never off its edge. */
.djh-dock--br { right: 16px; bottom: calc(16px + env(safe-area-inset-bottom, 0px)); }
.djh-dock--bl { left: 16px; bottom: calc(16px + env(safe-area-inset-bottom, 0px)); }
.djh-dock--tr { right: 16px; top: calc(16px + env(safe-area-inset-top, 0px)); flex-direction: column-reverse; }
.djh-dock--tl { left: 16px; top: calc(16px + env(safe-area-inset-top, 0px)); flex-direction: column-reverse; }
.djh-dock--bl .djh-fab, .djh-dock--tl .djh-fab { align-self: flex-start; }
/* Transform-only motion, promoted up front so the first frame of a drag never jitters.
   While held there is deliberately no transition: the dock follows the hand 1:1. The
   settle on release is applied inline by the FLIP effect; reduced-motion users get the
   corner change with no travel at all. */
.djh-dock { will-change: transform; transform-origin: center; }
.djh-dock--dragging { transition: none !important; }
.djh-dock--dragging * { pointer-events: none !important; }
@media (prefers-reduced-motion: no-preference) {
  /* The lift's shadow deepens by fading a second layer in, never by animating box-shadow. */
  .djh-dock--dragging .djh-bar,
  .djh-dock--dragging .djh-knobs,
  .djh-dock--dragging .djh-fab { position: relative; }
  .djh-bar::after, .djh-knobs::after, .djh-fab::after {
    content: ""; position: absolute; inset: 0; border-radius: inherit; pointer-events: none;
    box-shadow: 0 24px 48px -12px rgba(0,0,0,.6);
    opacity: 0; transition: opacity 150ms ease-out;
  }
  .djh-dock--dragging .djh-bar::after,
  .djh-dock--dragging .djh-knobs::after,
  .djh-dock--dragging .djh-fab::after { opacity: 1; }
}

/* Header: run name plus the two panel-level actions (move, hide). Kept out of the
   sections so every button inside a section is about that section's subject. */
.djh-head {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 8px 6px 6px;
  border-bottom: var(--hair) solid var(--line);
}
.djh-title {
  flex: 1 1 auto; min-width: 0;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font: 600 11px/1 ui-monospace, monospace; letter-spacing: .04em; color: var(--dim);
}
/* Section head: the label on the left, that section's own actions on the right. */
.djh-zone-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 22px; }
.djh-row--tight { gap: 4px; }
.djh-btn--sm { min-height: 22px; padding: 2px 8px; font-size: 11px; }
.djh-name {
  width: 9em; padding: 1px 6px; border-radius: 4px;
  font: inherit; color: inherit; background: transparent;
  border: 1px solid currentColor; border-color: color-mix(in srgb, currentColor 35%, transparent);
}
.djh-name:focus-visible { outline: 2px solid #6366f1; outline-offset: 1px; }
.djh-status {
  display: flex; align-items: center; gap: 6px; margin: -2px 0 0;
  font-size: 11px; color: var(--dim);
}
.djh-status-dot { width: 6px; height: 6px; border-radius: 999px; background: #5c5c64; flex: none; }
.djh-status-dot--on { background: #4ade80; }
.djh-row--more { margin-top: 2px; padding-top: 8px; border-top: var(--hair) solid var(--line); }
.djh-more-label {
  font-size: 9px; font-weight: 700; letter-spacing: .1em; text-transform: uppercase;
  color: var(--dim); margin-right: 2px;
}
.djh-grip {
  display: flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border: none; border-radius: 4px;
  color: #5c5c64; background: transparent; cursor: grab;
  touch-action: none; user-select: none;
}
.djh-grip:hover { color: #a1a1aa; background: rgba(255,255,255,.05); }
.djh-grip:active, .djh-dock--dragging .djh-grip { cursor: grabbing; }
.djh-grip:focus-visible { outline: 2px solid #fff; outline-offset: 2px; }
.djh-fab { cursor: grab; touch-action: none; }
.djh-fab:active { cursor: grabbing; }

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
 * what you send back (Feedback). One primary action in the whole bar — Copy all notes —
 * so the submit is never ambiguous; everything else is a quiet ghost button.
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
.djh-fab:active { transform: scale(0.96); }
.djh-fab:focus-visible { outline: 2px solid #fff; outline-offset: 2px; }

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
.djh-btn:active:not(:disabled), .djh-icon:active:not(:disabled) { transform: scale(0.96); }
.djh-btn--on { color: #fff; background: var(--accent); }
/* The submit takes its own full-width line: it is the one primary action, and it must not
   be mistaken for another chip in the row above it. */
.djh-btn--primary {
  flex: 1 0 100%; justify-content: center; margin-top: 2px;
  color: #fff; background: var(--accent); font-weight: 600;
}
.djh-btn--primary:hover:not(:disabled) { background: #6b6be0; }
.djh-btn:disabled, .djh-icon:disabled { color: #5c5c64; background: rgba(255,255,255,.04); cursor: default; }
/* Neutral focus rings, not the accent — a brand-coloured outline fights the accent it is
   drawn next to, and here it would sit on top of the very button it marks. */
.djh-btn:focus-visible, .djh-icon:focus-visible, .djh-seg-btn:focus-visible, .djh-scrub:focus-visible {
  outline: 2px solid #fff; outline-offset: 2px;
}
@media (prefers-reduced-motion: no-preference) {
  .djh-btn, .djh-icon, .djh-seg-btn {
    transition: background-color 150ms ease-out, color 150ms ease-out, transform 150ms ease-out;
  }
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
/* Freshness is stated, not implied: "updated 12s ago" says this is a poll, not a feed. */
.djh-fresh {
  display: inline-flex; align-items: center; gap: 4px;
  font-weight: 600; letter-spacing: .04em; text-transform: none; color: var(--dim);
  font-variant-numeric: tabular-nums;
}
.djh-fresh-btn {
  font: inherit; cursor: pointer; color: var(--dim);
  padding: 0 4px; border: none; border-radius: 4px; background: transparent;
  font-size: 12px; line-height: 1;
}
.djh-fresh-btn--text {
  font-size: 9px; font-weight: 700; letter-spacing: .04em; text-transform: none;
  color: #c7d2fe; text-decoration: underline; text-underline-offset: 2px;
}
.djh-fresh-btn:hover { color: var(--txt); background: rgba(255,255,255,.06); }
.djh-fresh-btn:focus-visible { outline: 2px solid #fff; outline-offset: 2px; }
@media (max-width: 680px) {
  .djh-dock { right: 12px; left: 12px; width: auto; max-width: none; }
  .djh-split { grid-template-columns: 1fr; grid-template-rows: 1fr 1fr; }
  .djh-side + .djh-side { border-left: none; border-top: 2px solid #0f0f12; }
}
`;
