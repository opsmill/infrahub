import React from "react";

const events = ["mousedown", "touchstart"] as const;

export function useOnClickOutside(
  ref: React.RefObject<HTMLElement | null> | null,
  handler: (event: PointerEvent | MouseEvent | TouchEvent | FocusEvent) => void
): void {
  const onOutsideClick = React.useEffectEvent(handler);

  React.useEffect(() => {
    const listener = (event: PointerEvent | MouseEvent | TouchEvent | FocusEvent) => {
      const el = ref?.current;
      if (!el || el.contains(event.target as Node)) return;

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
