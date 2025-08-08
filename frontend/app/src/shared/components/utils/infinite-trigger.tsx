import { ScrollAreaProps } from "@/shared/components/ui/scroll-area";
import React from "react";

import React from "react";

export interface InfiniteTriggerProps extends React.HTMLAttributes<HTMLDivElement> {
  hasNextPage: boolean;
  onLoadMore: () => void;
}

export const InfiniteTrigger = ({
  children,
  hasNextPage,
  onLoadMore,
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
  }, [onLoadMore, hasNextPage]);

  return (
    <div {...props} ref={rootRef}>
      {children}
      <div ref={loadMoreRef} className="h-px" />
    </div>
  );
};
