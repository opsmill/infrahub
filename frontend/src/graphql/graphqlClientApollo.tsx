import {
  ApolloClient,
  DefaultOptions,
  InMemoryCache,
  Observable,
  createHttpLink,
  from,
} from "@apollo/client";
import { setContext } from "@apollo/client/link/context";
import { onError } from "@apollo/client/link/error";
import fetch from "cross-fetch";
import { toast } from "react-toastify";
import { ALERT_TYPES, Alert } from "../components/alert";
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

const errorLink = onError(({ graphQLErrors, operation, forward }) => {
  if (graphQLErrors) {
    for (const graphQLError of graphQLErrors) {
      console.error(
        `[GraphQL error]: Message: ${graphQLError.message}, Location: ${JSON.stringify(
          graphQLError.locations
        )}, Path: ${graphQLError.path}`
      );

      return new Observable((observer) => {
        switch (graphQLError.extensions.code) {
          case 401: {
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
            break;
          }
          default:
            if (graphQLError.message) {
              toast(<Alert type={ALERT_TYPES.ERROR} message={graphQLError.message} />);
            }
        }
      });
    }
  }
});

const graphqlClient = new ApolloClient({
  link: from([errorLink, authLink, httpLink]),
  cache: new InMemoryCache(),
  defaultOptions,
});

export default graphqlClient;
