import React from "react";

const events = ["mousedown", "touchstart"] as const;

/**
 * Checks if the target element is inside a portal container.
 * Portals render as direct children of document.body outside the main app root (#root).
 */
function isInsidePortal(target: Node | null): boolean {
  if (!target || !(target instanceof Element)) return false;

  // Walk up to find if we're in a direct child of body that's not the main app
  let current: Element | null = target;
  while (current && current !== document.body) {
    if (current.parentElement === document.body) {
      // This is a direct child of body - if it's not #root, it's a portal
      return current.id !== "root";
    }
    current = current.parentElement;
  }

  return false;
}

export function useOnClickOutside(
  ref: React.RefObject<HTMLElement | null> | null,
  handler: (event: PointerEvent | MouseEvent | TouchEvent | FocusEvent) => void
): void {
  const onOutsideClick = React.useEffectEvent(handler);

  React.useEffect(() => {
    const listener = (event: PointerEvent | MouseEvent | TouchEvent | FocusEvent) => {
      const el = ref?.current;
      const target = event.target as Node;

      // Don't trigger if:
      // 1. No ref element
      // 2. Click is inside the ref element
      // 3. Click is inside a portal (body-level element outside #root)
      if (!el || el.contains(target) || isInsidePortal(target)) return;

      onOutsideClick(event);
    };

    events.forEach((event) => {
      document.addEventListener(event, listener);
    });

    return () => {
      events.forEach((event) => {
        document.removeEventListener(event, listener);
      });
    };
  }, [ref]);
}
