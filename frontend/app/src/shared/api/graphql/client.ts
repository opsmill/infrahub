import {
  type AnyVariables,
  Client,
  type CombinedError,
  type DocumentInput,
  fetchExchange,
  formatDocument,
  makeOperation,
  mapExchange,
} from "@urql/core";
import { authExchange } from "@urql/exchange-auth";

import { ERROR_CODES } from "@/shared/api/errors";
import { handleGraphQLErrors, hasCatalogueCode } from "@/shared/api/graphql/error-handling";
import type { GraphQLRequestContext, GraphQLResult } from "@/shared/api/graphql/types";
import { DEFAULT_PRIORITY, PRIORITY_HEADER } from "@/shared/api/priority";
import { queryClient } from "@/shared/api/rest/client";
import { CONFIG } from "@/shared/config/config";

import { getAccessToken } from "@/entities/authentication/api/token-storage";
import { redirectToLogin } from "@/entities/authentication/domain/use-cases/redirect-to-login";
import { refreshAccessTokenQueryOptions } from "@/entities/authentication/ui/queries/refresh-access-token.query";

// biome-ignore lint/performance/noBarrelFile: Re-exported so authoring and running a query need only this module.
export { graphql, type ResultOf, type VariablesOf } from "gql.tada";

// Add `__typename` to every selection set
const addTypenameExchange = mapExchange({
  onOperation: (operation) =>
    makeOperation(
      operation.kind,
      { ...operation, query: formatDocument(operation.query) },
      operation.context
    ),
});

const authenticationExchange = authExchange(async (authUtilities) => {
  return {
    addAuthToOperation: (operation) => {
      const accessToken = getAccessToken();
      if (!accessToken) return operation;

      return authUtilities.appendHeaders(operation, { Authorization: `Bearer ${accessToken}` });
    },
    didAuthError: (error) => {
      return hasCatalogueCode(error, ERROR_CODES.TOKEN_EXPIRED);
    },
    refreshAuth: async () => {
      await queryClient.fetchQuery(refreshAccessTokenQueryOptions()).catch((error) => {
        redirectToLogin();
        throw error;
      });
    },
  };
});

const clientsByEndpoint = new Map<string, Client>();

// urql's Client dedups concurrent operations by hash(query, variables) and ignores the URL.
// but this app carries the branch/point-in-time in the URL, not in variables.
// Without this, two concurrent identical query+variables on DIFFERENT branches share one network request
// and both receive one branch's data.
function getGraphqlClient(branch?: string | null, date?: Date | null): Client {
  const url = CONFIG.GRAPHQL_URL(branch, date);
  let client = clientsByEndpoint.get(url);
  if (!client) {
    client = new Client({
      url,
      requestPolicy: "network-only",
      preferGetMethod: false,
      fetchOptions: {
        headers: {
          [PRIORITY_HEADER]: DEFAULT_PRIORITY,
        },
      },
      exchanges: [addTypenameExchange, authenticationExchange, fetchExchange],
    });
    clientsByEndpoint.set(url, client);
  }
  return client;
}

// Map urql result to the preserved `{ data, errors }` shape and run error routing.
function toGraphQLResult<TData>(
  data: TData | undefined,
  error: CombinedError | undefined,
  context?: GraphQLRequestContext
): GraphQLResult<TData> {
  handleGraphQLErrors(error, context);

  if (error?.networkError) {
    throw error.networkError;
  }

  const errors = error?.graphQLErrors?.length
    ? error.graphQLErrors.map((e) => ({ message: e.message }))
    : undefined;

  return { data: data as TData, error: errors ? error : undefined, errors };
}

interface QueryArgs<TData, TVars extends AnyVariables> {
  query: DocumentInput<TData, TVars>;
  variables?: TVars;
  context?: GraphQLRequestContext;
}

interface MutateArgs<TData, TVars extends AnyVariables> {
  mutation: DocumentInput<TData, TVars>;
  variables?: TVars;
  context?: GraphQLRequestContext;
}

// The transport-only client the app depends on.
// Preserves the Apollo api: `query`/`mutate` returning `Promise<{ data, errors }>`.
export const graphqlClient = {
  async query<TData = any, TVars extends AnyVariables = AnyVariables>(
    args: QueryArgs<TData, TVars>
  ): Promise<GraphQLResult<TData>> {
    const result = await getGraphqlClient(args.context?.branch, args.context?.date)
      .query<TData, TVars>(args.query, args.variables as TVars)
      .toPromise();
    return toGraphQLResult(result.data, result.error, args.context);
  },

  async mutate<TData = any, TVars extends AnyVariables = AnyVariables>(
    args: MutateArgs<TData, TVars>
  ): Promise<GraphQLResult<TData>> {
    const result = await getGraphqlClient(args.context?.branch, args.context?.date)
      .mutation<TData, TVars>(args.mutation, args.variables as TVars)
      .toPromise();
    return toGraphQLResult(result.data, result.error, args.context);
  },
};
