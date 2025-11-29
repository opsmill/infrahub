import { apiClient } from "@/shared/api/rest/client";
import type { components } from "@/shared/api/rest/types.generated";
import { REFRESH_TOKEN_KEY } from "@/shared/config/constants";

import {
  removeTokensInLocalStorage,
  saveTokensInLocalStorage,
} from "@/entities/authentication/utils";

export type RefreshAccessToken = () => Promise<components["schemas"]["AccessTokenResponse"]>;

export const refreshAccessToken: RefreshAccessToken = async () => {
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);

  if (!refreshToken) {
    removeTokensInLocalStorage();
    window.location.reload();
    throw new Error("Refresh token not found");
  }

  const { data, error } = await apiClient.POST("/api/auth/refresh", {
    headers: {
      authorization: `Bearer ${refreshToken}`,
    },
  });

  if (error) {
    removeTokensInLocalStorage();
    window.location.reload();
    throw error;
  }

  saveTokensInLocalStorage(data);
  return data;
};
