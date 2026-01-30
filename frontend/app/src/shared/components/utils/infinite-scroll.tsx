import React from "react";

import { ScrollArea, type ScrollAreaProps } from "@/shared/components/ui/scroll-area";

export interface InfiniteScrollProps extends ScrollAreaProps {
  hasNextPage: boolean;
  onLoadMore: () => void;
  threshold?: number;
}

export const InfiniteScroll = ({
  children,
  hasNextPage,
  onLoadMore,
  threshold = 200,
  ...props
}: InfiniteScrollProps) => {
  const rootRef = React.useRef<HTMLDivElement>(null);
  const loadMoreRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && hasNextPage) {
            onLoadMore();
          }
        });
      },
      {
        root: rootRef.current,
        rootMargin: `0px 0px ${threshold}px 0px`,
      }
    );

    const currentContainer = loadMoreRef.current;
    if (currentContainer) {
      observer.observe(currentContainer);
    }

    return () => {
      observer.disconnect();
    };
  }, [onLoadMore, hasNextPage, threshold]);

  return (
    <ScrollArea {...props} ref={rootRef}>
      {children}
      <div ref={loadMoreRef} className="-mt-px h-px" aria-hidden="true" />
    </ScrollArea>
  );
};
