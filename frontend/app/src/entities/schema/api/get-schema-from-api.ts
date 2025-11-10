import { apiClient } from "@/shared/api/rest/client";
import type { ContextParams } from "@/shared/api/types";

export type GetSchemaFromApiParams = ContextParams;

export const getSchemaFromApi = ({ branchName, atDate }: GetSchemaFromApiParams) => {
  return apiClient.GET("/api/schema", {
    params: {
      query: {
        branch: branchName,
        date: atDate,
      },
    },
  });
};
