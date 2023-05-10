import { ApolloClient, InMemoryCache } from "@apollo/client";
import { CONFIG } from "../config/config";

const graphqlClient = new ApolloClient({
  uri: (operation) => {
    const context = operation.getContext();
    console.log("context: ", context);

    console.log("CONFIG.GRAPHQL_URL(context?.branch):", CONFIG.GRAPHQL_URL(context?.branch));
    return CONFIG.GRAPHQL_URL(context?.branch);
  },
  cache: new InMemoryCache(),
});

export default graphqlClient;
