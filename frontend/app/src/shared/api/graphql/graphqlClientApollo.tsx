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
        return retryWithRefreshedToken(operation, forward);

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
// the previous inline Observable block in errorLink — behaviour unchanged.
function retryWithRefreshedToken(
  operation: Parameters<Parameters<typeof onError>[0]>[0]["operation"],
  forward: Parameters<Parameters<typeof onError>[0]>[0]["forward"]
): Observable<FetchResult> {
  return new Observable<FetchResult>((observer) => {
    const oldHeaders = operation.getContext().headers;

    queryClient
      .fetchQuery(refreshAccessTokenQueryOptions())
      .then((newToken) => {
        if (newToken?.access_token) {
          operation.setContext({
            headers: {
              ...oldHeaders,
              authorization: newToken?.access_token,
            },
          });

          // Retry the failed request.
          const subscriber = {
            next: observer.next.bind(observer),
            error: observer.error.bind(observer),
            complete: observer.complete.bind(observer),
          };

          forward(operation).subscribe(subscriber);
        }
      })
      .catch((err) => observer.error(err));

    forward(operation);
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
