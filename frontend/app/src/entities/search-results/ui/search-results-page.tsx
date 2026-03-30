import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";

import Content from "@/shared/components/layout/content";
import { Skeleton } from "@/shared/components/loading/skeleton";
import { InfiniteTrigger } from "@/shared/components/utils/infinite-trigger";

import { groupSearchResultsByKind } from "@/entities/search-results/domain/group-search-results-by-kind";
import { useSearchResultsCount } from "@/entities/search-results/ui/queries/get-search-results-count.query";
import { useSearchResults } from "@/entities/search-results/ui/queries/search-results.query";
import { SearchResultsGroup } from "@/entities/search-results/ui/search-results-group";
import { SearchResultsHeader } from "@/entities/search-results/ui/search-results-header";

export function SearchResultsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const query = searchParams.get("q") ?? "";
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set());

  useEffect(() => {
    setOpenGroups(new Set());
  }, [query]);

  const {
    data: totalCount,
    isSuccess: isCountSuccess,
    isError: isCountError,
  } = useSearchResultsCount({ search: query }, { enabled: !!query });

  const { data, isPending, hasNextPage, fetchNextPage, isFetchingNextPage } = useSearchResults(
    { search: query, totalCount },
    { enabled: !!query && (isCountSuccess || isCountError) }
  );

  const allResults = useMemo(() => data?.pages.flat() ?? [], [data?.pages]);
  const groups = useMemo(() => groupSearchResultsByKind(allResults), [allResults]);

  const handleQueryChange = useCallback(
    (newQuery: string) => {
      setSearchParams({ q: newQuery });
    },
    [setSearchParams]
  );

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

  const allKinds = groups.map((g) => g.kind);
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
        totalCount={totalCount ?? 0}
        onQueryChange={handleQueryChange}
        allExpanded={allExpanded}
        hasMultipleGroups={groups.length > 1}
        onToggleAll={toggleAll}
      />

      <div className="flex flex-col gap-2 p-2">
        {isPending && query && (
          <Content.Card className="flex flex-col gap-3 p-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </Content.Card>
        )}

        {!isPending && query && groups.length === 0 && (
          <Content.Card className="py-12 text-center text-gray-500">
            No results found for &ldquo;{query}&rdquo;
          </Content.Card>
        )}

        {!query && (
          <Content.Card className="py-12 text-center text-gray-500">
            Enter a search query to find results
          </Content.Card>
        )}

        {groups.map((group) => (
          <SearchResultsGroup
            key={group.kind}
            kind={group.kind}
            results={group.results}
            isOpen={openGroups.has(group.kind)}
            onToggle={() => toggleGroup(group.kind)}
          />
        ))}

        <InfiniteTrigger
          hasNextPage={hasNextPage}
          onLoadMore={fetchNextPage}
          isFetchingNextPage={isFetchingNextPage}
        />

        {isFetchingNextPage && (
          <Content.Card className="flex flex-col gap-3 p-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </Content.Card>
        )}
      </div>
    </Content>
  );
}
