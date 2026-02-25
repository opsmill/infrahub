import { queryOptions, useQuery } from "@tanstack/react-query";
import { useAtomValue } from "jotai";

import type { ContextParams, QueryConfig } from "@/shared/api/types";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import {
  type SearchResultsFromApiParams,
  searchResultsFromApi,
} from "@/entities/search-results/api/search-results";
import { searchResultsQueryKeys } from "@/entities/search-results/domain/search-results.query-keys";
import type { SearchResultsGroup } from "@/entities/search-results/types";

export function groupSearchResultsByKind(
  results: Array<{ id: string; kind: string }>
): SearchResultsGroup[] {
  const groupMap = new Map<string, { kind: string; ids: string[] }>();
  for (const result of results) {
    const existing = groupMap.get(result.kind);
    if (existing) {
      existing.ids.push(result.id);
    } else {
      groupMap.set(result.kind, { kind: result.kind, ids: [result.id] });
    }
  }

  return Array.from(groupMap.values())
    .map((group) => ({
      kind: group.kind,
      label: group.kind,
      count: group.ids.length,
      results: group.ids.map((id) => ({ id, kind: group.kind })),
    }))
    .sort((a, b) => b.count - a.count);
}

async function fetchAndGroupSearchResults(params: SearchResultsFromApiParams) {
  const { data, errors } = await searchResultsFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  if (!data?.InfrahubSearchAnywhere) {
    return { totalCount: 0, groups: [] };
  }

  const { InfrahubSearchAnywhere } = data;
  const totalCount = InfrahubSearchAnywhere.count;
  const results = InfrahubSearchAnywhere.edges?.map(({ node }) => node) ?? [];

  const groups = groupSearchResultsByKind(results);

  return { totalCount, groups };
}

export function searchResultsQueryOptions(params: SearchResultsFromApiParams) {
  return queryOptions({
    queryKey: searchResultsQueryKeys.paginated(params),
    queryFn: () => fetchAndGroupSearchResults(params),
  });
}

export function useSearchResults(
  params: Omit<SearchResultsFromApiParams, keyof ContextParams>,
  config?: QueryConfig<typeof searchResultsQueryOptions>
) {
  const { currentBranch } = useCurrentBranch();
  const timeMachineDate = useAtomValue(datetimeAtom);

  return useQuery({
    ...searchResultsQueryOptions({
      branchName: currentBranch.name,
      atDate: timeMachineDate,
      ...params,
    }),
    ...config,
  });
}
