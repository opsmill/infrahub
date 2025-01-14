import { QueryClient } from "@tanstack/react-query";
import createClient, { Middleware } from "openapi-fetch";

import { INFRAHUB_API_SERVER_URL } from "@/config/config";

import { ACCESS_TOKEN_KEY } from "@/config/localStorage";
import { getNewToken } from "@/entities/authentication/ui/useAuth";
import type { paths } from "@/shared/api/rest/types.generated";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

export const apiClient = createClient<paths>({ baseUrl: INFRAHUB_API_SERVER_URL });

const authMiddleware: Middleware = {
  async onRequest({ request }) {
    const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);

    if (!accessToken) return request;

    request.headers.set("Authorization", `Bearer ${accessToken}`);
    return request;
  },
  async onResponse({ request, response }) {
    if (response.status === 401) {
      try {
        const newToken = await getNewToken();

        if (!newToken?.access_token) {
          return response;
        }

        request.headers.set("Authorization", `Bearer ${newToken.access_token}`);
        return fetch(request);
      } catch (error) {
        console.error(error);
        return response;
      }
    }
  },
};

apiClient.use(authMiddleware);
