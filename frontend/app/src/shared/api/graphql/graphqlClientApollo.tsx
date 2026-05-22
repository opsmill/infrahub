import { ApolloClient, type DefaultOptions, from, InMemoryCache, Observable } from "@apollo/client";
import { setContext } from "@apollo/client/link/context";
import { onError } from "@apollo/client/link/error";
import createUploadLink from "apollo-upload-client/createUploadLink.mjs";
import { toast } from "react-toastify";

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

// Error link to refresh token or display error
export const errorLink = onError(({ graphQLErrors, operation, forward }) => {
  if (graphQLErrors) {
    for (const graphQLError of graphQLErrors) {
      console.error(
        `[GraphQL error]: Message: ${graphQLError.message}, Location: ${JSON.stringify(
          graphQLError.locations
        )}, Path: ${graphQLError.path}`
      );

      const code = graphQLError.extensions?.code;
      if (code === "AUTHENTICATION_REQUIRED" || code === "TOKEN_EXPIRED") {
        return new Observable((observer) => {
          // Modify the operation context with a new token
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

                // Retry the failed request
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

      if (code === "PERMISSION_DENIED") {
        // Do not display alert on unauthorized errors
        return;
      }

      const { processErrorMessage } = operation.getContext();

      if (graphQLError.message && processErrorMessage) {
        processErrorMessage(graphQLError.message);
      } else if (graphQLError.message) {
        toast(<Alert type={ALERT_TYPES.ERROR} message={graphQLError.message} />, {
          toastId: "alert-error",
        });
      }
    }
  }
});

const graphqlClient = new ApolloClient({
  link: from([errorLink, authLink, httpLink]),
  cache: new InMemoryCache(),
  defaultOptions,
});

export default graphqlClient;
