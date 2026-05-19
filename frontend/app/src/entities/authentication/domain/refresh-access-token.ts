import type { components } from "@/shared/api/rest/types.generated";

import { refreshAccessTokenFromApi } from "@/entities/authentication/api/refresh-access-token-from-api";
import { REFRESH_TOKEN_KEY } from "@/entities/authentication/constants";
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

  let data;
  try {
    data = await refreshAccessTokenFromApi(refreshToken);
  } catch (error) {
    removeTokensInLocalStorage();
    window.location.reload();
    throw error;
  }

  saveTokensInLocalStorage(data);
  return data;
};
