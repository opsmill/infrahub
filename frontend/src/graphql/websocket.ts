import { SubscriptionClient } from "subscriptions-transport-ws";
import { CONFIG } from "../config/config";
import { WebSocketLink } from "@apollo/client/link/ws";
import { ApolloClient, InMemoryCache, from } from "@apollo/client";
import { defaultOptions, authLink, errorLink } from "./graphqlClientApollo";

export class WSClient {
  branch: string | undefined;
  subscription: any;
  link: any;
  client: any;

  getClient(branch?: string) {
    // Does not create a new client if the branch remains the same
    if (branch === this.branch) {
      return this.client;
    }

    // Sets the new branch
    this.branch = branch;

    // Closes the old web socket subscription
    if (this.subscription) {
      this.subscription.close();
    }

    // // Subscription client
    // this.subscription = createClient({
    //   url: CONFIG.GRAPHQL_WEB_SOCKET_URL(branch),
    //   connectionParams: {},
    // });

    // // Web socket link for apollo client
    // this.link = new GraphQLWsLink(this.subscription);

    // Subscription client (not maintained)
    this.subscription = new SubscriptionClient(CONFIG.GRAPHQL_WEB_SOCKET_URL(branch), {
      reconnect: true,
    });

    // Web socket link for apollo client
    this.link = new WebSocketLink(this.subscription);

    // Creates the apollo client
    this.client = new ApolloClient({
      link: from([errorLink, authLink, this.link]),
      cache: new InMemoryCache(),
      defaultOptions,
    });

    return this.client;
  }
}
