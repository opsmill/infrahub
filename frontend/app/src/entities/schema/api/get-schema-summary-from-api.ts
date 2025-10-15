import { apiClient } from "@/shared/api/rest/client";
import type { ContextParams } from "@/shared/api/types";

export type GetSchemaSummaryFromApiParams = ContextParams;

export const getSchemaSummaryFromApi = ({ branchName, atDate }: GetSchemaSummaryFromApiParams) => {
  return apiClient.GET("/api/schema/summary", {
    params: {
      query: {
        branch: branchName,
        date: atDate,
      },
    },
  });
};
