import { QueryClient } from "@tanstack/react-query";
import createClient, { type Middleware } from "openapi-fetch";

import type { paths } from "@/shared/api/rest/types.generated";
import { INFRAHUB_API_SERVER_URL } from "@/shared/config/config";
import { ACCESS_TOKEN_KEY } from "@/shared/config/localStorage";

import { refreshAccessTokenQueryOptions } from "@/entities/authentication/domain/refresh-access-token.query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: false,
    },
  },
});

export const apiClient = createClient<paths>({ baseUrl: INFRAHUB_API_SERVER_URL });

// Store cloned requests for retry purposes
const requestClones = new WeakMap<Request, Request>();

const authMiddleware: Middleware = {
  async onRequest({ request }) {
    const hadAuth = request.headers.has("Authorization");
    if (hadAuth) return request;

    const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
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

      if (!newToken?.access_token) {
        return response;
      }

      clonedRequest.headers.set("Authorization", `Bearer ${newToken.access_token}`);
      return fetch(clonedRequest);
    } catch (error) {
      console.error("Token refresh failed:", error);
      return response;
    }
  },
};

apiClient.use(authMiddleware);
