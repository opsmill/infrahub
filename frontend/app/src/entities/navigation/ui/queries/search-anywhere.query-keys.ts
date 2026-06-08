import type { SearchAnywhereParams } from "@/entities/navigation/domain/search-anywhere";
import type { SearchDocsParams } from "@/entities/navigation/domain/search-docs";

export const searchAnywhereQueryKeys = {
  objects: ({ branchName, search, atDate, caseSensitive }: SearchAnywhereParams) => [
    branchName,
    atDate,
    "search-objects",
    search,
    caseSensitive,
  ],
  docs: ({ query, limit }: SearchDocsParams) => ["search-docs", query, limit],
} as const;
