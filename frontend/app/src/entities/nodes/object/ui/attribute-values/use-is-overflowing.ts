import { useLayoutEffect, useRef, useState } from "react";

/** Whether an element's content is wider than the element, kept up to date as either resizes. */
export function useIsOverflowing<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [isOverflowing, setIsOverflowing] = useState(false);

  useLayoutEffect(() => {
    const element = ref.current;
    if (!element) return;

    const observer = new ResizeObserver(() =>
      setIsOverflowing(element.scrollWidth > element.clientWidth)
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return { ref, isOverflowing };
}
