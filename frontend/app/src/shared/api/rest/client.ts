import { QueryClient } from "@tanstack/react-query";
import createClient, { type Middleware } from "openapi-fetch";

import { PRIORITY_HEADER, resolvePriority } from "@/shared/api/priority";
import type { paths } from "@/shared/api/rest/types.generated";
import { INFRAHUB_API_SERVER_URL } from "@/shared/config/config";

import { getAccessToken } from "@/entities/authentication/api/token-storage";
import { redirectToLogin } from "@/entities/authentication/domain/use-cases/redirect-to-login";
import { refreshAccessTokenQueryOptions } from "@/entities/authentication/ui/queries/refresh-access-token.query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
      staleTime: 2000,
    },
  },
});

export const apiClient = createClient<paths>({ baseUrl: INFRAHUB_API_SERVER_URL });

// Store cloned requests for retry purposes
const requestClones = new WeakMap<Request, Request>();

export const authMiddleware: Middleware = {
  async onRequest({ request }) {
    // The backend prioritizes by X-Priority under load - UI requests are always high.
    request.headers.set(PRIORITY_HEADER, resolvePriority(request.headers.get(PRIORITY_HEADER)));

    const hadAuth = request.headers.has("Authorization");
    if (hadAuth) return request;

    const accessToken = getAccessToken();
    if (!accessToken) return request;

    request.headers.set("Authorization", `Bearer ${accessToken}`);

    // Store a clone for potential retry to avoid "body already used" error
    // This is necessary because Request bodies can only be consumed once
    requestClones.set(request, request.clone());

    return request;
  },
  async onResponse({ request, response }) {
    if (response.status !== 401) {
      requestClones.delete(request);
      return response;
    }

    const clonedRequest = requestClones.get(request);
    requestClones.delete(request);

    if (!clonedRequest) {
      return response;
    }

    try {
      const newToken = await queryClient.fetchQuery(refreshAccessTokenQueryOptions());

      clonedRequest.headers.set("Authorization", `Bearer ${newToken.access_token}`);
      return fetch(clonedRequest);
    } catch (error) {
      console.error("Token refresh failed:", error);
      redirectToLogin();
      return response;
    }
  },
};

apiClient.use(authMiddleware);
