/**
 * Annotation layer for a design-jam prototype. Prototype-only chrome — never shipped.
 *
 * Pointing at the thing is the whole point: "the second column header, next to the branch
 * name" costs a sentence to write, a sentence to misread, and a round trip to correct.
 * A pin costs a click.
 *
 * Controlled: it draws pins and captures clicks; the notes themselves live in whatever
 * `useNotesStore` decided — this browser, or the Infrahub instance the prototype runs in.
 *
 * See SKILL.md § Iterating inside the prototype.
 */

import { type ReactNode, useRef, useState } from "react";
import { createPortal } from "react-dom";

import type { NewNote, Note, NoteStatus } from "./notes-store";

export type { Note, NoteStatus } from "./notes-store";

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

/*
 * A pin on the app chrome around the prototype (sidebar, header) has no place in the pane's
 * box, so it is stored against the viewport instead, with a selector rooted at the document.
 * A pane selector never starts at `body`, which is what tells the two apart on render.
 */
const isViewportPin = (n: Note) => n.selector === "body" || n.selector.startsWith("body >");

type Props = {
  scope: string;
  notes: Note[];
  isMine: (n: Note) => boolean;
  onAdd: (note: NewNote) => Promise<void>;
  onUpdate: (
    id: string,
    patch: Partial<Pick<Note, "text" | "status" | "resolution">>
  ) => Promise<void>;
  onRemove: (id: string) => Promise<void>;
  armed: boolean;
  onArmedChange: (armed: boolean) => void;
  children: ReactNode;
};

const STATUSES: NoteStatus[] = ["open", "addressed", "declined", "deferred"];

export function Annotations({
  scope,
  notes,
  isMine,
  onAdd,
  onUpdate,
  onRemove,
  armed,
  onArmedChange,
  children,
}: Props) {
  const [openId, setOpenId] = useState<string | null>(null);
  /** Text being typed, per note, so a poll refresh can't yank the caret mid-sentence. */
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const rootRef = useRef<HTMLDivElement>(null);

  /**
   * Fired on the shield, not on the design. Two reasons it has to work this way:
   * a click handler is too late — menus, popovers and selects open on `pointerdown` — and
   * a pass-through overlay lets buttons fire, focus move and forms submit while you are
   * only trying to point at them. The shield eats the event, then briefly disables its own
   * hit-testing so `elementFromPoint` reports what is underneath rather than the shield.
   *
   * The shield covers the whole viewport, not just the pane: feedback is often about the
   * chrome around the prototype, and a layer that stops at the pane edge reads as "you may
   * only comment in here".
   */
  const onCapture = async (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();

    const shield = e.currentTarget;
    const root = rootRef.current;
    if (!root) return;

    shield.style.pointerEvents = "none";
    const target = document.elementFromPoint(e.clientX, e.clientY);
    shield.style.pointerEvents = "";
    if (!target) return;

    const snippet = (target.textContent ?? "").trim().slice(0, 60);
    onArmedChange(false);

    if (!root.contains(target)) {
      await onAdd({
        scope,
        selector: pathFrom(document.documentElement, target),
        snippet,
        x: e.clientX / window.innerWidth,
        y: e.clientY / window.innerHeight,
        text: "",
      });
      return;
    }

    const box = root.getBoundingClientRect();
    await onAdd({
      scope,
      selector: pathFrom(root, target),
      snippet,
      // `box` is the scrolling content's own rect, so these offsets already account for
      // how far the pane is scrolled. Fractions keep pins put across resizes.
      x: (e.clientX - box.left) / box.width,
      y: (e.clientY - box.top) / box.height,
      text: "",
    });
  };

  const commitText = (n: Note) => {
    const draft = drafts[n.id];
    if (draft === undefined || draft === n.text) return;
    onUpdate(n.id, { text: draft });
    setDrafts(({ [n.id]: _done, ...rest }) => rest);
  };

  const pin = (n: Note, i: number) => {
    const mine = isMine(n);
    const status = n.status ?? "open";
    return (
      <div
        key={n.id}
        className={isViewportPin(n) ? "dja-pin dja-pin--viewport" : "dja-pin"}
        style={{ left: `${n.x * 100}%`, top: `${n.y * 100}%` }}
      >
        <button
          type="button"
          className={[
            "dja-dot",
            !n.text && "dja-dot--empty",
            n.sentAt && "dja-dot--sent",
            status !== "open" && `dja-dot--${status}`,
          ]
            .filter(Boolean)
            .join(" ")}
          aria-label={`Note ${i + 1}${n.author ? ` by ${n.author}` : ""}${status !== "open" ? ` (${status})` : ""}: ${n.text || "empty"}`}
          onClick={() => setOpenId(openId === n.id ? null : n.id)}
        >
          {i + 1}
        </button>

        {openId === n.id && (
          <div className="dja-card">
            <p className="dja-target" title={n.selector}>
              {n.snippet || n.selector || "element"}
              {n.sentAt && <span className="dja-tag">sent</span>}
            </p>
            {n.author && (
              <p className="dja-author">
                {n.author}
                {!mine && <span className="dja-tag dja-tag--muted">read only</span>}
              </p>
            )}
            <textarea
              autoFocus={mine}
              readOnly={!mine}
              rows={3}
              value={drafts[n.id] ?? n.text}
              placeholder="What should change here?"
              onChange={(e) => setDrafts({ ...drafts, [n.id]: e.target.value })}
              onBlur={() => commitText(n)}
            />
            <div className="dja-triage" role="group" aria-label="Triage">
              {STATUSES.map((s) => (
                <button
                  key={s}
                  type="button"
                  aria-pressed={status === s}
                  className={status === s ? "dja-tri dja-tri--on" : "dja-tri"}
                  onClick={() => onUpdate(n.id, { status: s })}
                >
                  {s}
                </button>
              ))}
            </div>
            <div className="dja-card-foot">
              <button
                type="button"
                disabled={!mine}
                onClick={() => {
                  onRemove(n.id);
                  setOpenId(null);
                }}
              >
                Delete
              </button>
              <button
                type="button"
                onClick={() => {
                  commitText(n);
                  setOpenId(null);
                }}
              >
                Done
              </button>
            </div>
          </div>
        )}
      </div>
    );
  };

  const numbered = notes.map((n, i) => ({ n, i }));

  return (
    <div className="dja-root" ref={rootRef}>
      <style>{css}</style>
      {children}

      {numbered.filter(({ n }) => !isViewportPin(n)).map(({ n, i }) => pin(n, i))}

      {/* Portaled to the body: a `position: fixed` element inside a transformed or
          overflow-clipped ancestor is clipped to that ancestor, not the viewport. */}
      {createPortal(
        <>
          {armed && (
            <div
              className="dja-shield"
              onPointerDown={onCapture}
              onContextMenu={(e) => e.preventDefault()}
            >
              <p className="dja-hint">Click anything to pin a note · Esc to cancel</p>
            </div>
          )}
          {numbered.filter(({ n }) => isViewportPin(n)).map(({ n, i }) => pin(n, i))}
        </>,
        document.body
      )}
    </div>
  );
}

const statusTag = (n: Note) => {
  const s = n.status ?? "open";
  if (s === "open") return "";
  return ` _[${s}${n.resolution ? `: ${n.resolution}` : ""}]_`;
};

export const notesToMarkdown = (notes: Note[]) =>
  notes
    .filter((n) => n.text.trim())
    .map(
      (n, i) =>
        `${i + 1}. **${n.snippet || n.selector || "element"}**${n.author ? ` (${n.author})` : ""} — ${n.text.trim()}${statusTag(n)}\n   \`${n.selector}\``
    )
    .join("\n");

const css = `
.dja-root { position: relative; min-height: 100%; }
/*
 * A real element, not a pseudo-element with pointer-events: none. It has to actually
 * swallow the pointer, or clicking a button to annotate it presses the button instead.
 * Above the pins too, so arming never re-opens an existing note by accident. Below the
 * dock, so Add note can still be pressed again to cancel.
 */
.dja-shield {
  position: fixed; inset: 0; z-index: var(--djh-z-annotate, 40);
  cursor: crosshair;
  outline: 2px dashed #6366f1; outline-offset: -2px;
  background: rgba(99,102,241,.04);
  touch-action: none; user-select: none;
}
.dja-hint {
  position: fixed; top: 8px; left: 50%; transform: translateX(-50%); margin: 0;
  padding: 5px 12px; border-radius: 999px;
  font: 600 12px/1 system-ui, sans-serif;
  color: #fff; background: #4f46e5;
  box-shadow: 0 2px 10px rgba(0,0,0,.25);
}
.dja-pin { position: absolute; z-index: 25; transform: translate(-50%, -50%); }
.dja-pin--viewport { position: fixed; z-index: calc(var(--djh-z-annotate, 40) - 1); }
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
.dja-dot--sent { color: #4f46e5; background: #fff; border-color: #4f46e5; }
/* Triage outcomes read at a glance from the pin itself: done, declined, parked. */
.dja-dot--addressed { color: #fff; background: #15803d; border-color: #fff; }
.dja-dot--declined { color: #fff; background: #71717a; border-color: #fff; text-decoration: line-through; }
.dja-dot--deferred { color: #1c1917; background: #fcd34d; border-color: #fff; }
.dja-dot:focus-visible { outline: 2px solid #18181b; outline-offset: 2px; }
.dja-card {
  position: absolute; top: 28px; left: 0; width: 272px;
  display: grid; gap: 8px; padding: 10px; border-radius: 8px;
  font: 400 13px/1.45 system-ui, sans-serif; color: #18181b;
  background: #fff; border: 1px solid #d4d4d8;
  box-shadow: 0 10px 30px rgba(0,0,0,.2);
}
.dja-target {
  margin: 0; font-weight: 600; font-size: 12px; color: #52525b;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.dja-author { margin: -4px 0 0; font-size: 11px; color: #71717a; display: flex; gap: 6px; align-items: center; }
.dja-tag {
  margin-left: 6px; padding: 1px 5px; border-radius: 3px;
  font-size: 10px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase;
  color: #4338ca; background: #e0e7ff;
}
.dja-tag--muted { margin-left: 0; color: #52525b; background: #f4f4f5; }
.dja-card textarea {
  font: inherit; width: 100%; resize: vertical;
  padding: 6px 8px; border-radius: 6px; border: 1px solid #d4d4d8;
}
.dja-card textarea[readonly] { background: #fafafa; color: #3f3f46; }
.dja-triage { display: flex; gap: 4px; flex-wrap: wrap; }
.dja-tri {
  font: 600 10px/1 system-ui, sans-serif; letter-spacing: .04em; text-transform: uppercase;
  cursor: pointer; padding: 5px 7px; border-radius: 999px;
  color: #52525b; background: #f4f4f5; border: 1px solid #e4e4e7;
}
.dja-tri--on { color: #fff; background: #3f3f46; border-color: #3f3f46; }
.dja-tri:focus-visible { outline: 2px solid #18181b; outline-offset: 2px; }
.dja-card-foot { display: flex; justify-content: space-between; gap: 8px; }
.dja-card-foot button {
  font: 500 12px/1 system-ui, sans-serif; cursor: pointer;
  padding: 6px 10px; border-radius: 6px;
  border: 1px solid #d4d4d8; background: #fafafa; color: #3f3f46;
}
.dja-card-foot button:disabled { opacity: .45; cursor: default; }
`;
