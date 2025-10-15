import type { SearchAnywhereParams } from "@/entities/search-anywhere/domain/search-anywhere";
import type { SearchDocsParams } from "@/entities/search-anywhere/domain/search-docs";

export const searchAnywhereQueryKeys = {
  objects: ({ branchName, search, atDate }: SearchAnywhereParams) => [
    branchName,
    atDate,
    "search-objects",
    search,
  ],
  docs: ({ query, limit }: SearchDocsParams) => ["search-docs", query, limit],
} as const;
