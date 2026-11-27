import { useQueryStates } from "nuqs";

import {
  SEARCH_RESULTS_PARAMS,
  SEARCH_RESULTS_URL_KEYS,
} from "@/entities/navigation/ui/routing/search-results-urls";

export function useSearchResultsParams() {
  return useQueryStates(SEARCH_RESULTS_PARAMS, {
    urlKeys: SEARCH_RESULTS_URL_KEYS,
    history: "push",
  });
}
