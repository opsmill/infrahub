import {
  type SearchResultsFromApiParams,
  searchResultsFromApi,
} from "@/entities/search-results/api/search-results";
import type { SearchResultItem } from "@/entities/search-results/types";

export type SearchResults = {
  totalCount: number;
  results: SearchResultItem[];
};

export async function getSearchResults(params: SearchResultsFromApiParams): Promise<SearchResults> {
  const { data, errors } = await searchResultsFromApi(params);

  if (errors) {
    throw new Error(errors.map((e) => e.message).join("; "));
  }

  if (!data?.InfrahubSearchAnywhere) {
    return { totalCount: 0, results: [] };
  }

  const { InfrahubSearchAnywhere } = data;
  const totalCount = InfrahubSearchAnywhere.count;
  const results = InfrahubSearchAnywhere.edges?.map(({ node }) => node) ?? [];

  return { totalCount, results };
}
