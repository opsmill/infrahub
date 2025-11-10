import React from "react";

export function usePreventScrollOnNumberInput() {
  const ref = React.useRef<HTMLInputElement | null>(null);

  React.useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const handleWheel = (e: WheelEvent) => {
      if (document.activeElement === el) {
        e.preventDefault();
      }
    };

    el.addEventListener("wheel", handleWheel, { passive: false });

    return () => el.removeEventListener("wheel", handleWheel);
  }, []);

  return ref;
}
