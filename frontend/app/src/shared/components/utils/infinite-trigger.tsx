import React from "react";

export interface InfiniteTriggerProps extends React.HTMLAttributes<HTMLDivElement> {
  hasNextPage: boolean;
  onLoadMore: () => void;
  isFetchingNextPage?: boolean;
  threshold?: number;
}

export const InfiniteTrigger = ({
  hasNextPage,
  onLoadMore,
  isFetchingNextPage,
  threshold = 200,
  ...props
}: InfiniteTriggerProps) => {
  const loadMoreRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && hasNextPage && !isFetchingNextPage) {
            onLoadMore();
          }
        });
      },
      { rootMargin: `${threshold}px 0px` }
    );

    const currentContainer = loadMoreRef.current;
    if (currentContainer) {
      observer.observe(currentContainer);
    }

    return () => {
      observer.disconnect();
    };
  }, [onLoadMore, hasNextPage, isFetchingNextPage]);

  return <div ref={loadMoreRef} className="h-px" aria-hidden="true" {...props} />;
};
