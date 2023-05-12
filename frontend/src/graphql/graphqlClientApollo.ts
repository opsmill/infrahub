import { ApolloClient, InMemoryCache } from "@apollo/client";
import { CONFIG } from "../config/config";

const graphqlClient = new ApolloClient({
  uri: (operation) => {
    const context = operation.getContext();

    return CONFIG.GRAPHQL_URL(context?.branch);
  },
  cache: new InMemoryCache(),
});

export default graphqlClient;
