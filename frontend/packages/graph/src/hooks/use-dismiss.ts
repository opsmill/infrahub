import { type RefObject, useEffect, useRef } from "react";

interface UseDismissOptions {
  /**
   * Pointer-downs inside this element are treated as "inside" and do NOT dismiss — pass the
   * element that toggles the layer (e.g. an external trigger button). Without it, clicking a
   * trigger that lives outside `ref` would dismiss on pointer-down and then immediately re-open
   * on the trigger's release, leaving the layer stuck open.
   */
  ignoreRef?: RefObject<HTMLElement | null>;
}

/**
 * Calls `onDismiss` on outside pointer-down or Escape keypress, while `active` (default: true).
 * The triggering event is passed through so callers can inspect it or stop propagation.
 */
export function useDismiss(
  ref: RefObject<HTMLElement | null>,
  onDismiss: (event: Event) => void,
  active = true,
  options?: UseDismissOptions
) {
  const onDismissRef = useRef(onDismiss);
  onDismissRef.current = onDismiss;
  const ignoreRef = options?.ignoreRef;

  useEffect(() => {
    if (!active) return;

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (ref.current?.contains(target)) return;
      if (ignoreRef?.current?.contains(target)) return;
      onDismissRef.current(event);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onDismissRef.current(event);
      }
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [ref, active, ignoreRef]);
}
