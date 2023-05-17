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
    console.log("context: ", context);

    console.log(
      "CONFIG.GRAPHQL_URL(context?.branch, context?.date);: ",
      CONFIG.GRAPHQL_URL(context?.branch, context?.date)
    );

    return CONFIG.GRAPHQL_URL(context?.branch, context?.date);
  },
  cache: new InMemoryCache(),
  defaultOptions,
});

export default graphqlClient;
