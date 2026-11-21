import React from "react";

export function useIsOverflowing<T extends HTMLElement>() {
  const ref = React.useRef<T>(null);
  const [isOverflowing, setIsOverflowing] = React.useState(false);

  React.useLayoutEffect(() => {
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
