import React from "react";

export interface InfiniteTriggerProps extends React.HTMLAttributes<HTMLDivElement> {
  hasNextPage: boolean;
  onLoadMore: () => void;
  isFetchingNextPage?: boolean;
}

export const InfiniteTrigger = ({
  hasNextPage,
  onLoadMore,
  isFetchingNextPage,
}: InfiniteTriggerProps) => {
  const loadMoreRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting && hasNextPage && !isFetchingNextPage) {
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
  }, [onLoadMore, hasNextPage, isFetchingNextPage]);

  return <div ref={loadMoreRef} className="h-px" aria-hidden="true" />;
};
