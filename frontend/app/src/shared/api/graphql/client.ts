import {
  type AnyVariables,
  Client,
  type CombinedError,
  type DocumentInput,
  fetchExchange,
  formatDocument,
  makeOperation,
  mapExchange,
  type OperationResult,
  type OperationResultSource,
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

// Grows only with the branch/point-in-time endpoints a session visits, and dies with the page.
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

// urql keeps an operation alive until its last subscriber leaves, and merges any identical
// operation raised in the meantime into that one instead of reaching the server. `toPromise()`
// only leaves once the response lands, so a caller that walks away from a request it no longer
// wants still holds the operation open, and the caller that replaces it is handed the abandoned
// request's snapshot. Unsubscribing on abort releases the operation so the replacement is a real
// round trip.
function resolveOperation<TResult extends OperationResult>(
  source: OperationResultSource<TResult>,
  signal?: AbortSignal
): Promise<TResult> {
  if (!signal) {
    return source.toPromise();
  }

  return resolveAbortableOperation(source, signal);
}

function resolveAbortableOperation<TResult extends OperationResult>(
  source: OperationResultSource<TResult>,
  signal: AbortSignal
): Promise<TResult> {
  if (signal.aborted) {
    return Promise.reject(signal.reason);
  }

  return new Promise<TResult>((resolve, reject) => {
    let unsubscribe: (() => void) | undefined;
    let isSettled = false;

    const settle = (): boolean => {
      if (isSettled) return false;
      isSettled = true;
      signal.removeEventListener("abort", onAbort);
      unsubscribe?.();
      return true;
    };

    function onAbort() {
      if (settle()) reject(signal.reason);
    }

    signal.addEventListener("abort", onAbort, { once: true });

    // Mirrors `toPromise()`: the first result that is neither stale nor a partial payload.
    const subscription = source.subscribe((result) => {
      if (result.stale || result.hasNext) return;
      if (settle()) resolve(result);
    });

    unsubscribe = () => subscription.unsubscribe();
    if (isSettled) unsubscribe();
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
    const result = await resolveOperation(
      getGraphqlClient(args.context?.branch, args.context?.date).query<TData, TVars>(
        args.query,
        args.variables as TVars
      ),
      args.context?.signal
    );
    return toGraphQLResult(result.data, result.error, args.context);
  },

  async mutate<TData = any, TVars extends AnyVariables = AnyVariables>(
    args: MutateArgs<TData, TVars>
  ): Promise<GraphQLResult<TData>> {
    const result = await resolveOperation(
      getGraphqlClient(args.context?.branch, args.context?.date).mutation<TData, TVars>(
        args.mutation,
        args.variables as TVars
      ),
      args.context?.signal
    );
    return toGraphQLResult(result.data, result.error, args.context);
  },
};
