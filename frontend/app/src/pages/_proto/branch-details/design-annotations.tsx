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

  const onCapture = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!armed) return;
    e.preventDefault();
    e.stopPropagation();

    const root = e.currentTarget;
    const box = root.getBoundingClientRect();
    const target = document.elementFromPoint(e.clientX, e.clientY);
    if (!target || !root.contains(target)) return;

    const note: Note = {
      id: `n${Date.now().toString(36)}`,
      selector: pathFrom(root, target),
      snippet: (target.textContent ?? "").trim().slice(0, 60),
      x: (e.clientX - box.left) / box.width,
      y: (e.clientY - box.top + root.scrollTop) / box.height,
      text: "",
      createdAt: new Date().toISOString(),
    };
    commit([...notes, note]);
    setOpenId(note.id);
    onArmedChange(false);
  };

  return (
    <div className={armed ? "dja-root dja-root--armed" : "dja-root"} onClickCapture={onCapture}>
      <style>{css}</style>
      {children}

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
.dja-root--armed, .dja-root--armed * { cursor: crosshair !important; }
.dja-root--armed::after {
  content: ""; position: absolute; inset: 0; z-index: 20;
  outline: 2px dashed #6366f1; outline-offset: -2px; pointer-events: none;
}
.dja-pin { position: absolute; z-index: 25; transform: translate(-50%, -50%); }
.dja-dot {
  width: 22px; height: 22px; border-radius: 50%; cursor: pointer;
  font: 600 11px/22px system-ui, sans-serif; text-align: center;
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
