import { queryOptions } from "@tanstack/react-query";

import { CONFIG } from "@/config/config";

import { fetchUrl } from "@/shared/api/rest/fetch";

export type DocResult = {
  title: string;
  url: string;
  breadcrumb: string[];
};

export const searchDocsQueryOptions = ({ query, limit = 3 }: { query: string; limit?: number }) => {
  return queryOptions<DocResult[]>({
    queryKey: ["search-docs", query, limit],
    queryFn: async () => {
      return await fetchUrl(CONFIG.SEARCH_URL(query, limit));
    },
    enabled: !!query,
  });
};
