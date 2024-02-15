import fetch from "cross-fetch";
import {
  ApolloClient,
  DefaultOptions,
  HttpLink,
  InMemoryCache,
  Observable,
  from,
} from "@apollo/client";
import { setContext } from "@apollo/client/link/context";
import { onError } from "@apollo/client/link/error";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../components/utils/alert";
import { CONFIG } from "../config/config";
import { ACCESS_TOKEN_KEY } from "../config/constants";
import { getNewToken } from "../decorators/withAuth";

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

// HTTP link with context to update graphql endpoint
const httpLink = new HttpLink({
  uri: (operation) => {
    const context = operation.getContext();

    // Initial value for url, will be overriden in useQuery
    return CONFIG.GRAPHQL_URL(context?.branch, context?.date);
  },
  fetch, // Provides fetch to ensure that it is available
});

// // Web socket link
// const wsLink2 = new GraphQLWsLink(
//   createClient({
//     url: CONFIG.GRAPHQL_WEB_SOCKET_URL(),
//     connectionParams: {},
//   })
// );

// // Web socket link (not maintained)
// const wsLink = new WebSocketLink(
//   new SubscriptionClient(CONFIG.GRAPHQL_WEB_SOCKET_URL(), {
//     reconnect: true,
//   })
// );

// // Test operation to use either WS or HTTP
// const splitLink = split(
//   ({ query }) => {
//     const definition = getMainDefinition(query);
//     return definition.kind === "OperationDefinition" && definition.operation === "subscription";
//   },
//   wsLink,
//   httpLink
// );

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

      switch (graphQLError.extensions?.code) {
        case 401: {
          return new Observable((observer) => {
            // Modify the operation context with a new token
            const oldHeaders = operation.getContext().headers;

            getNewToken()
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
        default:
          if (graphQLError.message) {
            toast(<Alert type={ALERT_TYPES.ERROR} message={graphQLError.message} />, {
              toastId: "alert-error",
            });
          }
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
