import { type RefObject, useEffect, useState } from "react";

export function useIsTruncated(ref: RefObject<HTMLElement | null>) {
  const [isTruncated, setIsTruncated] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(() => {
      setIsTruncated(el.scrollWidth > el.clientWidth);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);

  return isTruncated;
}
