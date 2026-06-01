import type { components } from "@/shared/api/rest/types.generated";

import { refreshAccessTokenFromApi } from "@/entities/authentication/api/refresh-access-token-from-api";
import { REFRESH_TOKEN_KEY } from "@/entities/authentication/constants";
import { saveTokensInLocalStorage } from "@/entities/authentication/utils";

export type RefreshAccessToken = () => Promise<components["schemas"]["AccessTokenResponse"]>;

// Throws on every failure mode (missing refresh token, API error). The caller
// is responsible for handling the failure — `retryWithRefreshedToken` in
// graphqlClientApollo.tsx catches the rejection and calls `redirectToLogin`.
// Previously this function did its own `window.location.reload()`, which
// dropped in-flight React Query state and double-navigated when the catch
// site also redirected.
export const refreshAccessToken: RefreshAccessToken = async () => {
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);

  if (!refreshToken) {
    throw new Error("Refresh token not found");
  }

  const data = await refreshAccessTokenFromApi(refreshToken);
  saveTokensInLocalStorage(data);
  return data;
};
