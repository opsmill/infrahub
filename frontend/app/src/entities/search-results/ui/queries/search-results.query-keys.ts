import type { ContextParams } from "@/shared/api/types";

export const searchResultsQueryKeys = {
  all: ({ branchName, atDate, search }: ContextParams & { search: string }) => [
    branchName,
    atDate,
    "search-results",
    search,
  ],
} as const;
