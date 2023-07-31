import { ApolloClient, DefaultOptions, InMemoryCache, createHttpLink } from "@apollo/client";
import { setContext } from "@apollo/client/link/context";
import { onError } from "@apollo/client/link/error";
import fetch from "cross-fetch";
import { CONFIG } from "../config/config";
import { ACCESS_TOKEN_KEY } from "../config/constants";
import { getNewToken } from "../decorators/withAuth";

const defaultOptions: DefaultOptions = {
  watchQuery: {
    fetchPolicy: "no-cache",
    errorPolicy: "all",
  },
  query: {
    fetchPolicy: "no-cache",
    errorPolicy: "all",
  },
};

const httpLink = createHttpLink({
  uri: (operation) => {
    const context = operation.getContext();

    return CONFIG.GRAPHQL_URL(context?.branch, context?.date);
  },
  fetch,
});

const authLink = setContext((_, { headers }) => {
  // Get the token from the session storage
  const accessToken = sessionStorage.getItem(ACCESS_TOKEN_KEY);

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

const errorLink = onError(({ graphQLErrors, operation, forward }) => {
  if (graphQLErrors) {
    graphQLErrors.forEach(async ({ message, locations, path, extensions }) => {
      console.error(`[GraphQL error]: Message: ${message}, Location: ${locations}, Path: ${path}`);

      switch (extensions?.code) {
        case 401: {
          // Modify the operation context with a new token
          const oldHeaders = operation.getContext().headers;

          const newToken = await getNewToken();

          if (newToken?.access_token) {
            operation.setContext({
              headers: {
                ...oldHeaders,
                authorization: newToken?.access_token,
              },
            });
          }

          // Retry the request, returning the new observable
          return forward(operation);
        }
      }
    });
  }
});

const graphqlClient = new ApolloClient({
  link: authLink.concat(errorLink).concat(httpLink),
  cache: new InMemoryCache(),
  defaultOptions,
});

export default graphqlClient;
