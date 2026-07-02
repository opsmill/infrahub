import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY } from "@/entities/authentication/constants";
import type { UserToken } from "@/entities/authentication/types";

// Token persistence is browser-storage I/O — an api/ (external data access)
// concern, not domain. Keeping it here lets domain use-cases call it via
// domain -> api (allowed) instead of reaching into localStorage directly.
export const saveTokensInLocalStorage = (result: Partial<UserToken>) => {
  if (result?.access_token) {
    localStorage.setItem(ACCESS_TOKEN_KEY, result?.access_token);
  }

  if (result?.refresh_token) {
    localStorage.setItem(REFRESH_TOKEN_KEY, result?.refresh_token);
  }
};

export const removeTokensInLocalStorage = () => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
};
