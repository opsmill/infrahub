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

import { ERROR_CODES, parseCatalogueError } from "@/shared/api/errors";
import { queryClient } from "@/shared/api/rest/client";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { CONFIG } from "@/shared/config/config";

import { ACCESS_TOKEN_KEY } from "@/entities/authentication/constants";
import { redirectToLogin } from "@/entities/authentication/domain/redirect-to-login";
import { refreshAccessTokenQueryOptions } from "@/entities/authentication/ui/queries/refresh-access-token.query";

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

type ErrorLinkArgs = Parameters<Parameters<typeof onError>[0]>[0];

// True iff a forwarded result still carries TOKEN_EXPIRED. Used inside
// `retryWithRefreshedToken` because Apollo's onError link routes results
// from the retried observable directly to the outer observer — it does
// NOT re-invoke `handleGraphQLAuthError`, so a persistent TOKEN_EXPIRED
// would otherwise leak through to the caller as a generic GraphQL error.
function resultHasTokenExpired(result: FetchResult): boolean {
  return (
    result.errors?.some(
      (e) => parseCatalogueError(e.extensions).code === ERROR_CODES.TOKEN_EXPIRED
    ) ?? false
  );
}

// Error link callback: route each catalogue code to its policy. The
// discriminated union is generated from `schema/error-catalogue.json` —
// regenerate with `pnpm generate:error-bindings`. Exported (not just inlined
// into `onError`) so tests can drive it directly without spinning up an
// Apollo link chain.
export function handleGraphQLAuthError({
  graphQLErrors,
  operation,
  forward,
}: ErrorLinkArgs): Observable<FetchResult> | undefined {
  if (!graphQLErrors) return;

  for (const graphQLError of graphQLErrors) {
    const parsed = parseCatalogueError(graphQLError.extensions);

    console.error(
      `[GraphQL error]: Code: ${parsed.code}, Message: ${graphQLError.message}, ` +
        `Location: ${JSON.stringify(graphQLError.locations)}, Path: ${graphQLError.path}`
    );

    switch (parsed.code) {
      case ERROR_CODES.TOKEN_EXPIRED:
        // The retry loop is bounded by construction: Apollo's onError
        // does not re-invoke this handler for results from the retried
        // observable, so we get exactly one refresh+replay attempt per
        // operation. Persistence is caught inside `retryWithRefreshedToken`.
        return retryWithRefreshedToken(operation, forward);

      case ERROR_CODES.AUTHENTICATION_REQUIRED:
        redirectToLogin();
        return;

      case ERROR_CODES.PERMISSION_DENIED:
        // Silent — 403s are handled by route-level guards, not toasts.
        // `continue` (not `return`) so any sibling errors in the same
        // response still reach their handlers.
        continue;

      case ERROR_CODES.UNDEFINED_ERROR:
        // Catalogue gap: the backend returned a code we don't recognise.
        // In dev builds, surface this loudly so engineers see it without
        // having to dig through devtools — a console.warn pointing at
        // where to register the code, plus a prefix on the toast so the
        // miss is visible during manual testing. Prod stays silent
        // (just the generic toast) to avoid leaking implementation noise.
        if (import.meta.env.DEV) {
          console.warn(
            "[catalogue gap] Unmatched error code surfaced as UNDEFINED_ERROR. " +
              "Register it in backend/infrahub/errors/catalogue.py, regenerate " +
              "the schema, and run `pnpm generate:error-bindings`.",
            { message: graphQLError.message, extensions: graphQLError.extensions }
          );
          notifyUser(`[catalogue gap] ${graphQLError.message}`, operation);
          return;
        }
        notifyUser(graphQLError.message, operation);
        return;

      default:
        notifyUser(graphQLError.message, operation);
    }
  }

  return;
}

export const errorLink = onError(handleGraphQLAuthError);

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
          // Refresh resolved but the server returned no token — treat it
          // like a refresh failure: clear stale credentials and bounce to
          // /login, otherwise the user is left signed-in against tokens
          // the server has already disowned.
          redirectToLogin();
          observer.error(new Error("Token refresh returned no access_token"));
          return;
        }

        operation.setContext({
          headers: {
            ...oldHeaders,
            authorization: `Bearer ${newToken.access_token}`,
          },
        });

        // Retry the failed request. Inspect the replayed result for a
        // repeated TOKEN_EXPIRED — Apollo will not re-enter our handler
        // for results that come back from this `forward` call, so this
        // is the only place we can detect a persistent expiry (clock
        // skew, malformed refreshed token, server-side revoke) and bail
        // to /login instead of leaking the error to the caller.
        forward(operation).subscribe({
          next: (result) => {
            if (resultHasTokenExpired(result)) {
              redirectToLogin();
              observer.error(new Error("TOKEN_EXPIRED persisted after refresh"));
              return;
            }
            observer.next(result);
          },
          error: observer.error.bind(observer),
          complete: observer.complete.bind(observer),
        });
      })
      .catch((err) => {
        // Refresh itself failed (refresh token expired, network error,
        // server-side revoke). Without this branch the caller saw a
        // network error, kept the stale credentials in localStorage,
        // and every subsequent query hit the same wall — the user was
        // effectively stuck until they cleared storage by hand. Bounce
        // to /login so they can re-authenticate.
        redirectToLogin();
        observer.error(err);
      });
  });
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
