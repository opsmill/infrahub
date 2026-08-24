import { apiClient } from "@/shared/api/rest/client";
import type { ContextParams } from "@/shared/api/types";

export function getMenuFromApi({ branchName, atDate }: ContextParams) {
  return apiClient.GET("/api/menu", {
    params: {
      query: {
        branch: branchName,
        date: atDate,
      },
    },
  });
}
