import type { SearchAnywhereParams } from "@/entities/navigation/domain/search-anywhere";
import type { SearchDocsParams } from "@/entities/navigation/domain/search-docs";

export const searchAnywhereQueryKeys = {
  objects: ({ branchName, search, atDate }: SearchAnywhereParams) => [
    branchName,
    atDate,
    "search-objects",
    search,
  ],
  docs: ({ query, limit }: SearchDocsParams) => ["search-docs", query, limit],
} as const;
