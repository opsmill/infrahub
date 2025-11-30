import { fetchUrl } from "@/shared/api/rest/fetch";
import { CONFIG } from "@/shared/config/config";

export interface SearchDocsParams {
  query: string;
  limit?: number;
}

export interface SearchDocResult {
  title: string;
  url: string;
  breadcrumb: string[];
}

export type SearchDocs = (params: SearchDocsParams) => Promise<Array<SearchDocResult>>;

export const searchDocs: SearchDocs = async ({ query, limit }) => {
  return fetchUrl(CONFIG.SEARCH_URL(query, limit));
};
