import type { PaginationParams } from "@/shared/api/types";

import type { SearchAnywhereParams } from "@/entities/navigation/domain/use-cases/search-anywhere";
import type { SearchDocsParams } from "@/entities/navigation/domain/use-cases/search-docs";

export type SearchObjectsKeyParams = Omit<SearchAnywhereParams, keyof PaginationParams>;

export const searchAnywhereQueryKeys = {
  objects: ({ branchName, search, atDate, caseSensitive }: SearchObjectsKeyParams) => [
    branchName,
    atDate,
    "search-objects",
    search,
    caseSensitive,
  ],
  docs: ({ query, limit }: SearchDocsParams) => ["search-docs", query, limit],
} as const;
