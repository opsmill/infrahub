import {
  ApolloClient,
  type DefaultOptions,
  type FetchResult,
  from,
  InMemoryCache,
  Observable,
} from "@apollo/client";
import { setContext } from "@apollo/client/link/context";
import { onError } from "@apollo/client/link/error";
import createUploadLink from "apollo-upload-client/createUploadLink.mjs";
import { toast } from "react-toastify";

import { ERROR_CODES, parseErrorExtensions } from "@/shared/api/graphql/errors";
import { queryClient } from "@/shared/api/rest/client";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { CONFIG } from "@/shared/config/config";

import { ACCESS_TOKEN_KEY } from "@/entities/authentication/constants";
import { refreshAccessTokenQueryOptions } from "@/entities/authentication/ui/queries/refresh-access-token.query";
import { removeTokensInLocalStorage } from "@/entities/authentication/utils";

export const defaultOptions: DefaultOptions = {
  watchQuery: {
    fetchPolicy: "no-cache",
    errorPolicy: "all",
  },
  query: {
    fetchPolicy: "no-cache",
    errorPolicy: "all",
  },
};

// HTTP link with context to update graphql endpoint (supports file uploads)
const httpLink = createUploadLink({
  uri: (operation: { getContext: () => { branch?: string; date?: Date | null } }) => {
    const context = operation.getContext();

    return CONFIG.GRAPHQL_URL(context?.branch, context?.date);
  },
});

// Auth link to add headers
export const authLink = setContext((_, previousContext) => {
  const { headers } = previousContext;

  // Get the token from the session storage
  const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);

  if (!accessToken) {
    return {
      headers,
    };
  }

  return {
    headers: {
      ...headers,
      authorization: `Bearer ${accessToken}`,
    },
  };
});

// Minimal structural type covering the bits of Apollo's `Operation` that
// `bumpAuthRetryCount` touches. Lets the helper stay unit-testable without
// pulling in Apollo's full type just to mock two methods.
type RetryableOperation = {
  getContext: () => { authRetryCount?: number; [key: string]: unknown };
  setContext: (patch: Record<string, unknown>) => void;
};

// Increment the per-operation auth-retry counter and return the new value.
// Callers use the returned count to break the TOKEN_EXPIRED → refresh →
// TOKEN_EXPIRED loop after the first retry (clock skew, server-side revoke,
// or a malformed refreshed token would otherwise loop the link forever).
export function bumpAuthRetryCount(operation: RetryableOperation): number {
  const next = (operation.getContext().authRetryCount ?? 0) + 1;
  operation.setContext({ authRetryCount: next });
  return next;
}

// Error link: route each catalogue code to its policy. The catalogue is
// mirrored in @/shared/api/graphql/errors until US2's generated bindings
// (T029) land — see dev/specs/infp-468-graphql-error-catalogue/.
export const errorLink = onError(({ graphQLErrors, operation, forward }) => {
  if (!graphQLErrors) return;

  for (const graphQLError of graphQLErrors) {
    const parsed = parseErrorExtensions(graphQLError.extensions);

    console.error(
      `[GraphQL error]: Code: ${parsed.code}, Message: ${graphQLError.message}, ` +
        `Location: ${JSON.stringify(graphQLError.locations)}, Path: ${graphQLError.path}`
    );

    switch (parsed.code) {
      case ERROR_CODES.TOKEN_EXPIRED:
        if (bumpAuthRetryCount(operation) > 1) return redirectToLogin();
        return retryWithRefreshedToken(operation, forward);

      case ERROR_CODES.AUTHENTICATION_REQUIRED:
        return redirectToLogin();

      case ERROR_CODES.PERMISSION_DENIED:
        // Silent — 403s are handled by route-level guards, not toasts.
        return;

      default:
        notifyUser(graphQLError.message, operation);
    }
  }

  return;
});

// Helper: refresh the access token and replay the operation. Lifted from
// the previous inline Observable block in errorLink; the only behaviour
// change is that a refresh resolving without an access_token now errors
// the observer instead of leaving it pending (the old code dropped the
// no-token branch silently and the request hung forever).
function retryWithRefreshedToken(
  operation: Parameters<Parameters<typeof onError>[0]>[0]["operation"],
  forward: Parameters<Parameters<typeof onError>[0]>[0]["forward"]
): Observable<FetchResult> {
  return new Observable<FetchResult>((observer) => {
    const oldHeaders = operation.getContext().headers;

    queryClient
      .fetchQuery(refreshAccessTokenQueryOptions())
      .then((newToken) => {
        if (!newToken?.access_token) {
          // Refresh resolved but the server returned no token — fail the
          // retry observable so the caller sees an error instead of hanging
          // forever. Apollo will surface this as a network error.
          observer.error(new Error("Token refresh returned no access_token"));
          return;
        }

        operation.setContext({
          headers: {
            ...oldHeaders,
            authorization: `Bearer ${newToken.access_token}`,
          },
        });

        // Retry the failed request.
        const subscriber = {
          next: observer.next.bind(observer),
          error: observer.error.bind(observer),
          complete: observer.complete.bind(observer),
        };

        forward(operation).subscribe(subscriber);
      })
      .catch((err) => observer.error(err));
  });
}

// Helper: token is invalid or missing — clear local credentials and bounce
// to /login. Hard-navigates because errorLink runs outside React Router,
// and the AuthProvider's localStorage hook does not re-render on external
// writes. Skips the redirect if we're already on /login to avoid loops.
//
// Encodes the current path as `?from=…` so `LoginPage` can route the user
// back to where they were after re-authenticating. The hard nav means
// `location.state` is gone, so the query string is the only carrier left.
function redirectToLogin(): void {
  removeTokensInLocalStorage();
  if (window.location.pathname === "/login") return;

  const from = window.location.pathname + window.location.search + window.location.hash;
  window.location.assign(`/login?from=${encodeURIComponent(from)}`);
}

// Helper: surface an error to the user. Calls operation.context's
// processErrorMessage if present (caller-specific override), else toasts.
function notifyUser(
  message: string | undefined,
  operation: Parameters<Parameters<typeof onError>[0]>[0]["operation"]
) {
  if (!message) return;

  const { processErrorMessage } = operation.getContext();

  if (processErrorMessage) {
    processErrorMessage(message);
    return;
  }

  toast(<Alert type={ALERT_TYPES.ERROR} message={message} />, {
    toastId: "alert-error",
  });
}

const graphqlClient = new ApolloClient({
  link: from([errorLink, authLink, httpLink]),
  cache: new InMemoryCache(),
  defaultOptions,
});

export default graphqlClient;
