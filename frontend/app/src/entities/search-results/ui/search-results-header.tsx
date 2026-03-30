import { Icon } from "@iconify-icon/react";
import { useEffect, useRef, useState } from "react";

import { SearchInput } from "@/shared/components/inputs/search-input";
import { Badge } from "@/shared/components/ui/badge";
import { useDebounce } from "@/shared/hooks/useDebounce";

type SearchResultsHeaderProps = {
  query: string;
  totalCount: number;
  onQueryChange: (query: string) => void;
  allExpanded: boolean;
  hasMultipleGroups: boolean;
  onToggleAll: () => void;
};

export function SearchResultsHeader({
  query,
  totalCount,
  onQueryChange,
  allExpanded,
  hasMultipleGroups,
  onToggleAll,
}: SearchResultsHeaderProps) {
  const [localQuery, setLocalQuery] = useState(query);
  const debouncedQuery = useDebounce(localQuery.trim(), 300);
  const isInitialMount = useRef(true);

  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }
    if (debouncedQuery !== query) {
      onQueryChange(debouncedQuery);
    }
  }, [debouncedQuery, query, onQueryChange]);

  return (
    <div className="flex h-14 items-center gap-2 px-3">
      <SearchInput
        value={localQuery}
        onChange={setLocalQuery}
        onSubmit={() => onQueryChange(localQuery.trim())}
        onPressReset={() => {
          setLocalQuery("");
          onQueryChange("");
        }}
        placeholder="Search..."
        className="h-8"
        aria-label="Search query"
      />

      <Badge variant="blue" className="shrink-0">
        {totalCount} {totalCount === 1 ? "result" : "results"}
      </Badge>

      {hasMultipleGroups && (
        <button
          type="button"
          onClick={onToggleAll}
          className="flex shrink-0 items-center gap-1.5 rounded px-2 py-1 text-gray-600 text-sm hover:bg-gray-100"
        >
          <Icon
            icon={allExpanded ? "mdi:unfold-less-horizontal" : "mdi:unfold-more-horizontal"}
            className="text-base"
          />
          {allExpanded ? "Collapse all" : "Expand all"}
        </button>
      )}
    </div>
  );
}
