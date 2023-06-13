import {
  ApolloClient,
  DefaultOptions,
  InMemoryCache,
  concat,
  createHttpLink,
} from "@apollo/client";
import { setContext } from "@apollo/client/link/context";
import { CONFIG } from "../config/config";
import { ACCESS_TOKEN_KEY } from "../config/constants";

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
      authorization: accessToken,
    },
  };
});

const graphqlClient = new ApolloClient({
  link: concat(authLink, httpLink),
  cache: new InMemoryCache(),
  defaultOptions,
});

export default graphqlClient;
