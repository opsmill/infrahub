import { CONFIG } from "@/config/config";
import { REFRESH_TOKEN_KEY } from "@/config/constants";
import { ACCESS_TOKEN_KEY } from "@/config/localStorage";

import { fetchUrl } from "@/shared/api/rest/fetch";

import { UserToken } from "@/entities/authentication/types";

export const saveTokensInLocalStorage = (result: Partial<UserToken>) => {
  if (result?.access_token) {
    localStorage.setItem(ACCESS_TOKEN_KEY, result?.access_token);
  }

  if (result?.refresh_token) {
    localStorage.setItem(REFRESH_TOKEN_KEY, result?.refresh_token);
  }
};

export const removeTokensInLocalStorage = async () => {
  const localToken = localStorage.getItem(ACCESS_TOKEN_KEY);

  const payload = {
    method: "POST",
    headers: {
      authorization: `Bearer ${localToken}`,
    },
  };

  await fetchUrl(CONFIG.LOGOUT_URL, payload);

  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
};
