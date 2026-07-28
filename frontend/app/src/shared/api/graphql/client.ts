import {
  type AnyVariables,
  Client,
  type CombinedError,
  createRequest,
  type DocumentInput,
  fetchExchange,
  formatDocument,
  makeOperation,
  mapExchange,
  type OperationContext,
} from "@urql/core";
import { authExchange } from "@urql/exchange-auth";

import { ERROR_CODES } from "@/shared/api/errors";
import { handleGraphQLErrors, hasCatalogueCode } from "@/shared/api/graphql/error-handling";
import type { GraphQLRequestContext, GraphQLResult } from "@/shared/api/graphql/types";
import { PRIORITY_HEADER, resolvePriority } from "@/shared/api/priority";
import { queryClient } from "@/shared/api/rest/client";
import { CONFIG, INFRAHUB_API_SERVER_URL } from "@/shared/config/config";

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

const client = new Client({
  url: INFRAHUB_API_SERVER_URL,
  requestPolicy: "network-only",
  preferGetMethod: false,
  exchanges: [addTypenameExchange, authenticationExchange, fetchExchange],
});

// Fold `str` into `seed` to derive a combined request key. Uses modular
// arithmetic (not bitwise) so it only needs to be deterministic and
// well-distributed enough to keep different URLs on different keys — not
// cryptographic. `MOD` is a prime near 2^31; the intermediate `hash * 33`
// stays well below 2^53, so no precision is lost.
function foldStringIntoKey(str: string, seed: number): number {
  const MOD = 2_147_483_647;
  let hash = seed % MOD;
  for (let i = 0; i < str.length; i++) {
    hash = (hash * 33 + str.charCodeAt(i)) % MOD;
  }
  return hash;
}

// urql's Client dedups concurrent operations by hash(query, variables)
// but this app carries the branch/point-in-time in the URL (context), not in variables.
// Without this, two concurrent identical query+variables on DIFFERENT branches share one network request
// and both receive one branch's data.
// Mutations don't need this, urql never dedups them.
function keyedQueryRequest<TData, TVars extends AnyVariables>(
  query: DocumentInput<TData, TVars>,
  variables: TVars,
  url: string | undefined
) {
  const request = createRequest<TData, TVars>(query, variables);
  if (url) request.key = foldStringIntoKey(url, request.key);
  return request;
}

// Build the per-operation urql context from a caller's request context:
// the branch/date-scoped endpoint URL and the X-Priority header. Authorization
// is added later by authExchange. Exported for tests.
export function buildOperationContext(context?: GraphQLRequestContext): Partial<OperationContext> {
  const date = typeof context?.date === "string" ? new Date(context.date) : context?.date;
  return {
    url: CONFIG.GRAPHQL_URL(context?.branch, date),
    requestPolicy: "network-only",
    fetchOptions: {
      headers: {
        [PRIORITY_HEADER]: resolvePriority(context?.priority),
      },
    },
  };
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

// The transport-only client the app depends on. Preserves the Apollo imperative
// interface: `query`/`mutate` returning `Promise<{ data, errors }>`.
export const graphqlClient = {
  async query<TData = any, TVars extends AnyVariables = AnyVariables>(
    args: QueryArgs<TData, TVars>
  ): Promise<GraphQLResult<TData>> {
    const context = buildOperationContext(args.context);
    const request = keyedQueryRequest<TData, TVars>(
      args.query,
      (args.variables ?? {}) as TVars,
      context.url
    );
    const result = await client.executeQuery<TData, TVars>(request, context).toPromise();
    return toGraphQLResult(result.data, result.error, args.context);
  },

  async mutate<TData = any, TVars extends AnyVariables = AnyVariables>(
    args: MutateArgs<TData, TVars>
  ): Promise<GraphQLResult<TData>> {
    const result = await client
      .mutation<TData, TVars>(
        args.mutation,
        (args.variables ?? {}) as TVars,
        buildOperationContext(args.context)
      )
      .toPromise();
    return toGraphQLResult(result.data, result.error, args.context);
  },
};
