import type { SearchAnywhereParams } from "@/entities/navigation/domain/use-cases/search-anywhere";
import type { SearchDocsParams } from "@/entities/navigation/domain/use-cases/search-docs";

export const searchAnywhereQueryKeys = {
  objects: ({
    branchName,
    search,
    limit,
    atDate,
    caseSensitive,
    exactMatch,
  }: SearchAnywhereParams) => [
    branchName,
    atDate,
    "search-objects",
    search,
    caseSensitive,
    exactMatch,
    limit,
  ],
  docs: ({ query, limit }: SearchDocsParams) => ["search-docs", query, limit],
} as const;
