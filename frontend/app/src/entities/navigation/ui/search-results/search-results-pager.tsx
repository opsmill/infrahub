import { Button } from "@infrahub/ui";

import { Icon } from "@/shared/components/display/icon";

import { formatSearchResultsWindow } from "@/entities/navigation/domain/rules/format-search-results-window";

interface SearchResultsPagerProps {
  page: number;
  offset: number;
  rowCount: number;
  hasMore: boolean;
  onPageChange: (page: number) => void;
}

export function SearchResultsPager({
  page,
  offset,
  rowCount,
  hasMore,
  onPageChange,
}: SearchResultsPagerProps) {
  if (page === 1 && !hasMore) return null;

  return (
    <nav
      aria-label="Search results pagination"
      className="flex flex-wrap items-center justify-between gap-2 border-t pt-2 pr-4 pl-2 text-sm"
    >
      <p className="text-foreground-muted tabular-nums" role="status">
        {formatSearchResultsWindow({ offset, rowCount })}
      </p>

      <div className="flex items-center gap-1">
        <Button
          variant="outline"
          size="sm"
          isDisabled={page <= 1}
          onPress={() => onPageChange(page - 1)}
        >
          <Icon icon="mdi:chevron-left" className="text-base" />
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          isDisabled={!hasMore}
          onPress={() => onPageChange(page + 1)}
        >
          Next
          <Icon icon="mdi:chevron-right" className="text-base" />
        </Button>
      </div>
    </nav>
  );
}
