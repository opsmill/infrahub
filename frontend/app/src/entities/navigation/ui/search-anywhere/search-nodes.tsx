import { Command, useCommandState } from "cmdk";
import { useAtomValue } from "jotai";
import React from "react";

import { CountBadge } from "@/shared/components/display/count-badge";
import { Icon } from "@/shared/components/display/icon";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { InfiniteTrigger } from "@/shared/components/utils/infinite-trigger";
import { useDebounce } from "@/shared/hooks/useDebounce";
import { formatNumberDisplay } from "@/shared/utils/number";

import type { ObjectResult } from "@/entities/navigation/domain/use-cases/search-anywhere";
import { searchCaseSensitiveAtom } from "@/entities/navigation/stores/search-case-sensitive.atom";
import {
  SEARCH_BATCH_SIZE,
  useGetSearchAnywhere,
} from "@/entities/navigation/ui/queries/search-anywhere.query";
import { getSearchResultsUrl } from "@/entities/navigation/ui/routing/search-results-urls";
import { SearchAnywhereGroup } from "@/entities/navigation/ui/search-anywhere/search-anywhere-group";
import { SearchAnywhereItem } from "@/entities/navigation/ui/search-anywhere/search-anywhere-item";
import {
  SearchResultNodeSummary,
  SearchResultNodeSummarySkeleton,
  useGetSearchResultObject,
} from "@/entities/navigation/ui/search-anywhere/search-result-node";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";

export const SearchNodes = () => {
  const query = useCommandState((state) => state.search);
  const queryDebounced = useDebounce(query.trim(), 300);
  const caseSensitive = useAtomValue(searchCaseSensitiveAtom);
  const viewportRef = React.useRef<HTMLDivElement>(null);

  const {
    data,
    isPending,
    isFetching,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    isFetchNextPageError,
  } = useGetSearchAnywhere(
    { search: queryDebounced, caseSensitive },
    { enabled: !!queryDebounced }
  );

  const rows = data?.matchingObjects ?? [];

  if (query.trim() === "") return null;

  if (isPending) {
    return (
      <SearchAnywhereGroup heading="Objects">
        <SearchAnywhereItem to="" disabled>
          Loading...
        </SearchAnywhereItem>
      </SearchAnywhereGroup>
    );
  }

  if (rows.length === 0) return null;

  return (
    <>
      <SearchAnywhereGroup
        heading={<SearchNodesHeading count={rows.length} hasMore={hasNextPage} />}
        className="min-h-26 shrink"
        viewportRef={viewportRef}
      >
        {rows.map((node) => (
          <NodesOptions key={node.id} node={node} />
        ))}

        <InfiniteTrigger
          hasNextPage={hasNextPage && !isFetching && !isFetchNextPageError}
          onLoadMore={fetchNextPage}
          rootRef={viewportRef}
        />

        <SearchNodesListEnd
          isLoadingMore={isFetchingNextPage}
          hasMore={hasNextPage}
          hasFailed={isFetchNextPageError}
          count={rows.length}
        />
      </SearchAnywhereGroup>

      <ShowAllSearchResults search={query.trim()} caseSensitive={caseSensitive} />
    </>
  );
};

interface ShowAllSearchResultsProps {
  search: string;
  caseSensitive: boolean;
}

const ShowAllSearchResults = ({ search, caseSensitive }: ShowAllSearchResultsProps) => (
  <SearchAnywhereGroup>
    <SearchAnywhereItem
      to={getSearchResultsUrl({ search, caseSensitive })}
      value="show-all-search-results"
    >
      <Icon icon="mdi:format-list-bulleted" className="px-2 text-lg" />
      Show all results for <span className="font-semibold">{search}</span>
    </SearchAnywhereItem>
  </SearchAnywhereGroup>
);

interface SearchNodesHeadingProps {
  count: number;
  hasMore: boolean;
}

const SearchNodesHeading = ({ count, hasMore }: SearchNodesHeadingProps) => (
  <span className="flex items-center gap-1.5">
    Objects <CountBadge variant="pill" count={count} hasMore={hasMore} />
  </span>
);

interface SearchNodesListEndProps {
  isLoadingMore: boolean;
  hasMore: boolean;
  hasFailed: boolean;
  count: number;
}

const SearchNodesListEnd = ({
  isLoadingMore,
  hasMore,
  hasFailed,
  count,
}: SearchNodesListEndProps) => {
  if (isLoadingMore) return <LoadingIndicator className="my-2 text-sm" />;

  if (hasFailed) {
    return (
      <div className="flex h-10 items-center justify-center text-subtle-muted text-xs">
        Could not load more results
      </div>
    );
  }

  if (hasMore || count <= SEARCH_BATCH_SIZE) return null;

  return (
    <div className="flex h-10 items-center justify-center text-subtle-muted text-xs">
      End of results · {formatNumberDisplay(count)} objects
    </div>
  );
};

type NodesOptionsProps = {
  node: ObjectResult;
};

export const NodesOptions = ({ node }: NodesOptionsProps) => {
  const { schema, object, isPending, error } = useGetSearchResultObject(node);

  if (!schema) return null;

  if (isPending) return <SearchResultNodeSkeleton />;

  if (error) return null;

  if (!object) return <div className="text-sm">No data found for this object</div>;

  const url = getObjectDetailsUrl(object.__typename, object.id);

  return (
    <SearchAnywhereItem to={url} value={url}>
      <SearchResultNodeSummary schema={schema} object={object} />
    </SearchAnywhereItem>
  );
};

export const SearchResultNodeSkeleton = () => {
  return (
    <Command.Item disabled className="flex w-full py-2">
      <SearchResultNodeSummarySkeleton />
    </Command.Item>
  );
};
