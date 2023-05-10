import { ApolloClient, DefaultOptions, InMemoryCache } from "@apollo/client";
import { CONFIG } from "./config";

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
  cache: new InMemoryCache({
    // dataIdFromObject(responseObject, other) {
    //   console.log("responseObject: ", responseObject);
    //   console.log("other: ", other);
    //   return JSON.stringify(responseObject);
    // },
  }),
  defaultOptions,
});

export default graphqlClient;
