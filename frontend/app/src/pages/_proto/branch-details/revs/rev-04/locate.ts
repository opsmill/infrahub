// PROTOTYPE — "take me to that error": reveal (page/expand), scroll, focus, briefly highlight.
import { useEffect } from "react";

// `instant`: the request came from the keyboard, so skip the smooth scroll.
export type LocateTarget = { kind: "band" | "task"; id: string; nonce: number; instant?: boolean };

export const bandDomId = (repoId: string) => `import-${repoId}`;
export const taskDomId = (taskId: string) => `task-row-${taskId}`;

// The target may only exist after the reveal state (page change, expanded bands, open accordion)
// renders, so poll for a few frames rather than assuming it is already in the DOM.
function focusWhenPresent(domId: string, instant: boolean, framesLeft = 20) {
  const el = document.getElementById(domId);
  if (!el) {
    if (framesLeft > 0)
      requestAnimationFrame(() => focusWhenPresent(domId, instant, framesLeft - 1));
    return;
  }
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  el.scrollIntoView({ behavior: reduce || instant ? "auto" : "smooth", block: "center" });
  el.focus({ preventScroll: true });
  el.setAttribute("data-located", "");
  window.setTimeout(() => el.removeAttribute("data-located"), 1600);
}

export function useLocate(
  target: LocateTarget | null,
  kind: LocateTarget["kind"],
  reveal: (id: string) => string | null
) {
  // biome-ignore lint/correctness/useExhaustiveDependencies: re-run only when a new locate request arrives
  useEffect(() => {
    if (!target || target.kind !== kind) return;
    const domId = reveal(target.id);
    if (domId) focusWhenPresent(domId, !!target.instant);
  }, [target?.nonce]);
}
