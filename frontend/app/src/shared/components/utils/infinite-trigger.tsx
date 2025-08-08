import React from "react";

export interface InfiniteTriggerProps extends React.HTMLAttributes<HTMLDivElement> {
  hasNextPage: boolean;
  onLoadMore: () => void;
  isFetchingNextPage?: boolean;
  threshold?: number;
}

export const InfiniteTrigger = ({
  children,
  hasNextPage,
  onLoadMore,
  isFetchingNextPage,
  threshold = 200,
  ...props
}: InfiniteTriggerProps) => {
  const rootRef = React.useRef<HTMLDivElement>(null);
  const loadMoreRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const root = rootRef.current ?? undefined;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && hasNextPage && !isFetchingNextPage) {
            onLoadMore();
          }
        });
      },
      {
        root,
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
  }, [onLoadMore, hasNextPage, isFetchingNextPage]);

  return (
    <div {...props} ref={rootRef}>
      {children}
      <div ref={loadMoreRef} className="h-px" aria-hidden="true" />
    </div>
  );
};
