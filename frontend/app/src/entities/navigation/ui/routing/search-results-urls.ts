import { createSerializer, parseAsBoolean, parseAsInteger, parseAsString } from "nuqs";

import { constructPath } from "@/shared/api/rest/fetch";

export const SEARCH_RESULTS_PATH = "/search";

export const SEARCH_RESULTS_PARAMS = {
  search: parseAsString.withDefault(""),
  caseSensitive: parseAsBoolean.withDefault(false),
  page: parseAsInteger.withDefault(1),
} as const;

export const SEARCH_RESULTS_URL_KEYS = {
  search: "q",
  caseSensitive: "case_sensitive",
  page: "page",
} as const;

const serializeSearchResultsParams = createSerializer(SEARCH_RESULTS_PARAMS, {
  urlKeys: SEARCH_RESULTS_URL_KEYS,
});

interface SearchResultsUrlParams {
  search: string;
  caseSensitive: boolean;
}

export function getSearchResultsUrl({ search, caseSensitive }: SearchResultsUrlParams): string {
  return constructPath(
    serializeSearchResultsParams(SEARCH_RESULTS_PATH, { search, caseSensitive })
  );
}
