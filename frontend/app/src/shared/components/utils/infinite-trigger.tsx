import { ScrollAreaProps } from "@/shared/components/ui/scroll-area";
import React from "react";

export interface InfiniteTriggerProps extends ScrollAreaProps {
  hasNextPage: boolean;
  onLoadMore: () => void;
  threshold?: number;
}

export const InfiniteTrigger = ({
  children,
  hasNextPage,
  onLoadMore,
  threshold = 200,
  ...props
}: InfiniteTriggerProps) => {
  const rootRef = React.useRef<HTMLDivElement>(null);
  const loadMoreRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting && hasNextPage) {
          onLoadMore();
        }
      });
    });

    const currentContainer = loadMoreRef.current;
    if (currentContainer) {
      observer.observe(currentContainer);
    }

    return () => {
      observer.disconnect();
    };
  }, [onLoadMore, hasNextPage, threshold]);

  return (
    <div {...props} ref={rootRef}>
      {children}
      <div ref={loadMoreRef} className="h-px" />
    </div>
  );
};
