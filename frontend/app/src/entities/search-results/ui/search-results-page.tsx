import { Icon } from "@iconify-icon/react";
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router";

import Content from "@/shared/components/layout/content";
import { Skeleton } from "@/shared/components/loading/skeleton";

import { useSearchResults } from "@/entities/search-results/domain/search-results.query";
import { SearchResultsGroup } from "@/entities/search-results/ui/search-results-group";
import { SearchResultsHeader } from "@/entities/search-results/ui/search-results-header";

export function SearchResultsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const query = searchParams.get("q") ?? "";
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set());

  useEffect(() => {
    setOpenGroups(new Set());
  }, [query]);

  const { data, isPending } = useSearchResults({ search: query, limit: 500 }, { enabled: !!query });

  function handleQueryChange(newQuery: string) {
    setSearchParams({ q: newQuery });
  }

  const toggleGroup = useCallback((kind: string) => {
    setOpenGroups((prev) => {
      const next = new Set(prev);
      if (next.has(kind)) {
        next.delete(kind);
      } else {
        next.add(kind);
      }
      return next;
    });
  }, []);

  const allKinds = data?.groups.map((g) => g.kind) ?? [];
  const allExpanded = allKinds.length > 0 && allKinds.every((k) => openGroups.has(k));

  function toggleAll() {
    if (allExpanded) {
      setOpenGroups(new Set());
    } else {
      setOpenGroups(new Set(allKinds));
    }
  }

  return (
    <Content>
      <Content.Title title={`Search results for "${query}"`} />

      <SearchResultsHeader
        query={query}
        totalCount={data?.totalCount ?? 0}
        onQueryChange={handleQueryChange}
      />

      <div className="flex flex-col gap-2 p-2">
        {isPending && query && (
          <Content.Card className="flex flex-col gap-3 p-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </Content.Card>
        )}

        {!isPending && query && data?.groups.length === 0 && (
          <Content.Card className="py-12 text-center text-gray-500">
            No results found for &ldquo;{query}&rdquo;
          </Content.Card>
        )}

        {!query && (
          <Content.Card className="py-12 text-center text-gray-500">
            Enter a search query to find results
          </Content.Card>
        )}

        {data && data.groups.length > 1 && (
          <div className="flex justify-end px-2">
            <button
              type="button"
              onClick={toggleAll}
              className="flex items-center gap-1.5 rounded px-2 py-1 text-gray-600 text-sm hover:bg-gray-100"
            >
              <Icon
                icon={allExpanded ? "mdi:unfold-less-horizontal" : "mdi:unfold-more-horizontal"}
                className="text-base"
              />
              {allExpanded ? "Collapse all" : "Expand all"}
            </button>
          </div>
        )}

        {data?.groups.map((group) => (
          <SearchResultsGroup
            key={group.kind}
            kind={group.kind}
            results={group.results}
            isOpen={openGroups.has(group.kind)}
            onToggle={() => toggleGroup(group.kind)}
          />
        ))}
      </div>
    </Content>
  );
}
