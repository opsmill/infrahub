import { ApolloClient, DefaultOptions, InMemoryCache } from "@apollo/client";
import { CONFIG } from "../config/config";

const defaultOptions: DefaultOptions = {
  watchQuery: {
    fetchPolicy: "no-cache",
    errorPolicy: "ignore",
  },
  query: {
    fetchPolicy: "no-cache",
    errorPolicy: "all",
  },
};

const graphqlClient = new ApolloClient({
  uri: (operation) => {
    const context = operation.getContext();

    return CONFIG.GRAPHQL_URL(context?.branch, context?.date);
  },
  cache: new InMemoryCache(),
  defaultOptions,
});

export default graphqlClient;
