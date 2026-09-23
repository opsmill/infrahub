/**
 * Annotation layer for a design-jam prototype. Prototype-only chrome — never shipped.
 *
 * Pointing at the thing is the whole point: "the second column header, next to the branch
 * name" costs a sentence to write, a sentence to misread, and a round trip to correct.
 * A pin costs a click.
 *
 * See SKILL.md § Iterating inside the prototype.
 */

import { type ReactNode, useEffect, useState } from "react";

export type Note = {
  id: string;
  /** CSS path from the pane root — best effort, may go stale across revisions. */
  selector: string;
  /** First words of the element's text. This is what actually finds it again. */
  snippet: string;
  /** Fraction of the pane box, so pins survive a resize. */
  x: number;
  y: number;
  text: string;
  createdAt: string;
  /** Set when the note has been sent. Sent notes stay visible but stop counting. */
  sentAt?: string;
};

const pathFrom = (root: Element, el: Element): string => {
  const parts: string[] = [];
  let node: Element | null = el;
  while (node && node !== root && parts.length < 8) {
    const parent: Element | null = node.parentElement;
    if (!parent) break;
    const tag = node.tagName.toLowerCase();
    const sameTag = Array.from(parent.children).filter((c) => c.tagName === node?.tagName);
    parts.unshift(sameTag.length > 1 ? `${tag}:nth-of-type(${sameTag.indexOf(node) + 1})` : tag);
    node = parent;
  }
  return parts.join(" > ");
};

const storageKey = (scope: string) => `design-jam:notes:${scope}`;

export const loadNotes = (scope: string): Note[] => {
  try {
    return JSON.parse(localStorage.getItem(storageKey(scope)) ?? "[]");
  } catch {
    return [];
  }
};

const saveNotes = (scope: string, notes: Note[]) => {
  try {
    localStorage.setItem(storageKey(scope), JSON.stringify(notes));
  } catch {
    /* private window, blocked storage — the session still works, it just won't persist */
  }
};

/**
 * Marks every unsent note in this scope as sent. Sent notes are kept, not deleted — the
 * agent may not have acted yet, and a note that vanishes on Send looks like data loss.
 */
export const markSent = (scope: string) => {
  const stamp = new Date().toISOString();
  const next = loadNotes(scope).map((n) => (n.sentAt ? n : { ...n, sentAt: stamp }));
  saveNotes(scope, next);
  return next;
};

type Props = {
  /** `<slug>:<variant>:rev<N>` — notes belong to one revision, not to the route. */
  scope: string;
  /** Bump to force a re-read from storage after an external change (e.g. Send). */
  refreshKey?: number;
  armed: boolean;
  onArmedChange: (armed: boolean) => void;
  onNotesChange: (notes: Note[]) => void;
  children: ReactNode;
};

export function Annotations({
  scope,
  refreshKey = 0,
  armed,
  onArmedChange,
  onNotesChange,
  children,
}: Props) {
  const [notes, setNotes] = useState<Note[]>(() => loadNotes(scope));
  const [openId, setOpenId] = useState<string | null>(null);

  useEffect(() => {
    const next = loadNotes(scope);
    setNotes(next);
    onNotesChange(next);
    setOpenId(null);
  }, [scope, refreshKey, onNotesChange]);

  const commit = (next: Note[]) => {
    setNotes(next);
    saveNotes(scope, next);
    onNotesChange(next);
  };

  /**
   * Fired on the shield, not on the design. Two reasons it has to work this way:
   * a click handler is too late — menus, popovers and selects open on `pointerdown` — and
   * a pass-through overlay lets buttons fire, focus move and forms submit while you are
   * only trying to point at them. The shield eats the event, then briefly disables its own
   * hit-testing so `elementFromPoint` reports what is underneath rather than the shield.
   */
  const onCapture = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();

    const shield = e.currentTarget;
    const root = shield.parentElement;
    if (!root) return;

    const box = root.getBoundingClientRect();
    shield.style.pointerEvents = "none";
    const target = document.elementFromPoint(e.clientX, e.clientY);
    shield.style.pointerEvents = "";
    if (!target || !root.contains(target)) return;

    const note: Note = {
      id: `n${Date.now().toString(36)}`,
      selector: pathFrom(root, target),
      snippet: (target.textContent ?? "").trim().slice(0, 60),
      // `box` is the scrolling content's own rect, so these offsets already account for
      // how far the pane is scrolled. Storing fractions keeps pins put across resizes.
      x: (e.clientX - box.left) / box.width,
      y: (e.clientY - box.top) / box.height,
      text: "",
      createdAt: new Date().toISOString(),
    };
    commit([...notes, note]);
    setOpenId(note.id);
    onArmedChange(false);
  };

  return (
    <div className="dja-root">
      <style>{css}</style>
      {children}

      {armed && (
        <div
          className="dja-shield"
          onPointerDown={onCapture}
          onContextMenu={(e) => e.preventDefault()}
        >
          <p className="dja-hint">Click anything to pin a note · Esc to cancel</p>
        </div>
      )}

      {notes.map((n, i) => (
        <div key={n.id} className="dja-pin" style={{ left: `${n.x * 100}%`, top: `${n.y * 100}%` }}>
          <button
            type="button"
            className={["dja-dot", !n.text && "dja-dot--empty", n.sentAt && "dja-dot--sent"]
              .filter(Boolean)
              .join(" ")}
            aria-label={`Note ${i + 1}${n.sentAt ? " (sent)" : ""}: ${n.text || "empty"}`}
            onClick={() => setOpenId(openId === n.id ? null : n.id)}
          >
            {i + 1}
          </button>

          {openId === n.id && (
            <div className="dja-card">
              <p className="dja-target" title={n.selector}>
                {n.snippet || n.selector || "element"}
                {n.sentAt && <span className="dja-sent-tag">sent</span>}
              </p>
              <textarea
                autoFocus
                rows={3}
                value={n.text}
                placeholder="What should change here?"
                onChange={(e) =>
                  commit(notes.map((m) => (m.id === n.id ? { ...m, text: e.target.value } : m)))
                }
              />
              <div className="dja-card-foot">
                <button
                  type="button"
                  onClick={() => {
                    commit(notes.filter((m) => m.id !== n.id));
                    setOpenId(null);
                  }}
                >
                  Delete
                </button>
                <button type="button" onClick={() => setOpenId(null)}>
                  Done
                </button>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export const notesToMarkdown = (notes: Note[]) =>
  notes
    .filter((n) => n.text.trim())
    .map(
      (n, i) =>
        `${i + 1}. **${n.snippet || n.selector || "element"}** — ${n.text.trim()}\n   \`${n.selector}\``
    )
    .join("\n");

const css = `
.dja-root { position: relative; min-height: 100%; }
/*
 * A real element, not a pseudo-element with pointer-events: none. It has to actually
 * swallow the pointer, or clicking a button to annotate it presses the button instead.
 * Above the pins too, so arming never re-opens an existing note by accident.
 */
.dja-shield {
  position: absolute; inset: 0; z-index: 26;
  cursor: crosshair;
  outline: 2px dashed #6366f1; outline-offset: -2px;
  background: rgba(99,102,241,.04);
  touch-action: none; user-select: none;
}
.dja-hint {
  position: sticky; top: 8px; margin: 8px auto 0; width: fit-content;
  padding: 5px 12px; border-radius: 999px;
  font: 600 12px/1 system-ui, sans-serif;
  color: #fff; background: #4f46e5;
  box-shadow: 0 2px 10px rgba(0,0,0,.25);
}
.dja-pin { position: absolute; z-index: 25; transform: translate(-50%, -50%); }
/* Flex centring rather than a line-height matched to the box: with a 2px border the text
   box and the circle no longer share a centre, and the number sits visibly low. */
.dja-dot {
  display: flex; align-items: center; justify-content: center;
  box-sizing: border-box;
  width: 24px; height: 24px; border-radius: 999px; padding: 0; cursor: pointer;
  font: 600 11px/1 system-ui, sans-serif;
  font-variant-numeric: tabular-nums;
  color: #fff; background: #4f46e5; border: 2px solid #fff;
  box-shadow: 0 1px 6px rgba(0,0,0,.35);
}
.dja-dot--empty { background: #a1a1aa; }
/* Sent notes stay on screen, hollowed out — visibly handled, not visibly lost. */
.dja-dot--sent { color: #4f46e5; background: #fff; border-color: #4f46e5; }
.dja-sent-tag {
  margin-left: 6px; padding: 1px 5px; border-radius: 3px;
  font-size: 10px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
  color: #4338ca; background: #e0e7ff;
}
.dja-dot:focus-visible { outline: 2px solid #a5b4fc; outline-offset: 2px; }
.dja-card {
  position: absolute; top: 28px; left: 0; width: 260px;
  display: grid; gap: 8px; padding: 10px; border-radius: 8px;
  font: 400 13px/1.45 system-ui, sans-serif; color: #18181b;
  background: #fff; border: 1px solid #d4d4d8;
  box-shadow: 0 10px 30px rgba(0,0,0,.2);
}
.dja-target {
  margin: 0; font-weight: 600; font-size: 12px; color: #52525b;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.dja-card textarea {
  font: inherit; width: 100%; resize: vertical;
  padding: 6px 8px; border-radius: 6px; border: 1px solid #d4d4d8;
}
.dja-card-foot { display: flex; justify-content: space-between; gap: 8px; }
.dja-card-foot button {
  font: 500 12px/1 system-ui, sans-serif; cursor: pointer;
  padding: 6px 10px; border-radius: 6px;
  border: 1px solid #d4d4d8; background: #fafafa; color: #3f3f46;
}
`;
