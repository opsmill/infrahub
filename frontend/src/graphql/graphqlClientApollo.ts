import { ApolloClient, DefaultOptions, InMemoryCache } from "@apollo/client";
import { CONFIG } from "../config/config";

const defaultOptions: DefaultOptions = {
  watchQuery: {
    fetchPolicy: "network-only",
    errorPolicy: "ignore",
  },
  query: {
    fetchPolicy: "network-only",
    errorPolicy: "all",
  },
};

const graphqlClient = new ApolloClient({
  uri: (operation) => {
    const context = operation.getContext();

    return CONFIG.GRAPHQL_URL(context?.branch);
  },
  cache: new InMemoryCache(),
  defaultOptions,
});

export default graphqlClient;
