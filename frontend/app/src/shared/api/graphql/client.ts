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

// A urql Client merges a query into an identical operation it already has in flight, keyed by
// hash(query, variables) — which carries neither the endpoint nor the moment the caller asked. Reusing
// a Client across calls therefore hands a caller a response computed before it asked: a refetch after
// a write, a poll, or an event-driven refresh can all resolve with pre-change data and nothing
// refetches again. React Query owns caching and deduplication here, so the transport keeps no state
// across calls — each call gets its own Client and therefore its own request.
function createGraphqlClient(branch?: string | null, date?: Date | null): Client {
  return new Client({
    url: CONFIG.GRAPHQL_URL(branch, date),
    preferGetMethod: false,
    fetchOptions: {
      headers: {
        [PRIORITY_HEADER]: DEFAULT_PRIORITY,
      },
    },
    exchanges: [addTypenameExchange, authenticationExchange, fetchExchange],
  });
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

  if (error?.graphQLErrors?.length) {
    throw new Error(error.graphQLErrors.map((e) => e.message).join("; "), { cause: error });
  }

  return { data: data as TData };
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
    const result = await createGraphqlClient(args.context?.branch, args.context?.date)
      .query<TData, TVars>(args.query, args.variables as TVars)
      .toPromise();
    return toGraphQLResult(result.data, result.error, args.context);
  },

  async mutate<TData = any, TVars extends AnyVariables = AnyVariables>(
    args: MutateArgs<TData, TVars>
  ): Promise<GraphQLResult<TData>> {
    const result = await createGraphqlClient(args.context?.branch, args.context?.date)
      .mutation<TData, TVars>(args.mutation, args.variables as TVars)
      .toPromise();
    return toGraphQLResult(result.data, result.error, args.context);
  },
};
