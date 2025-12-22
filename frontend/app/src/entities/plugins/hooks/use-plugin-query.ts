import { gql, useQuery as useApolloQuery } from "@apollo/client";
import { useAtomValue } from "jotai";
import { useMemo } from "react";

import { CONFIG } from "@/shared/config/config";

import { currentBranchAtom } from "@/entities/branches/stores";

import type { PluginQueryConfig } from "../types";

interface UsePluginQueryOptions {
  /** Query configuration from the plugin manifest */
  queryConfig?: PluginQueryConfig;
  /** Variables to pass to the query */
  variables?: Record<string, unknown>;
  /** Whether to skip the query */
  skip?: boolean;
  /** Object ID to include in query variables */
  objectId?: string;
}

interface UsePluginQueryResult<T = unknown> {
  data?: T;
  loading: boolean;
  error?: Error;
  refetch: () => void;
}

// Placeholder query used when no real query is configured
// This is needed because Apollo's useQuery hook validates the query even when skipped
const PLACEHOLDER_QUERY = gql`
  query PluginPlaceholder {
    __typename
  }
`;

// Query to fetch a saved CoreGraphQLQuery by name
const SAVED_QUERY_LOOKUP = gql`
  query GetSavedQuery($name: String!) {
    CoreGraphQLQuery(name__value: $name) {
      edges {
        node {
          id
          query {
            value
          }
        }
      }
    }
  }
`;

/**
 * Hook to execute a plugin's GraphQL query
 *
 * Supports both:
 * - Saved queries: Fetches the query from CoreGraphQLQuery by name, then executes it
 * - Inline queries: Executes the query string directly
 */
export function usePluginQuery<T = unknown>({
  queryConfig,
  variables = {},
  skip = false,
  objectId,
}: UsePluginQueryOptions): UsePluginQueryResult<T> {
  const branch = useAtomValue(currentBranchAtom);

  const isSavedQuery = queryConfig?.type === "saved";
  const isInlineQuery = queryConfig?.type === "inline";

  // For saved queries, first fetch the query definition
  const {
    data: savedQueryData,
    loading: savedQueryLoading,
    error: savedQueryError,
  } = useApolloQuery(SAVED_QUERY_LOOKUP, {
    skip: skip || !isSavedQuery,
    variables: { name: isSavedQuery ? queryConfig.name : "" },
    context: {
      uri: CONFIG.GRAPHQL_URL(branch?.name),
    },
  });

  // Extract the actual query string
  const queryString = useMemo(() => {
    if (!queryConfig) return null;

    if (isInlineQuery) {
      return queryConfig.query;
    }

    if (isSavedQuery && savedQueryData) {
      const edges = savedQueryData?.CoreGraphQLQuery?.edges;
      if (edges && edges.length > 0) {
        return edges[0]?.node?.query?.value;
      }
    }

    return null;
  }, [queryConfig, isInlineQuery, isSavedQuery, savedQueryData]);

  // Parse the query string into a gql document
  const queryDocument = useMemo(() => {
    if (!queryString) return null;
    try {
      return gql(queryString);
    } catch (e) {
      console.error("[Plugin Query] Failed to parse query:", e);
      return null;
    }
  }, [queryString]);

  // Determine if we should skip the plugin query
  const shouldSkipPluginQuery = skip || !queryConfig || !queryDocument;

  // Execute the actual plugin query
  // Use PLACEHOLDER_QUERY when the real query isn't available to satisfy Apollo's validation
  const {
    data: pluginData,
    loading: pluginLoading,
    error: pluginError,
    refetch,
  } = useApolloQuery(queryDocument ?? PLACEHOLDER_QUERY, {
    skip: shouldSkipPluginQuery,
    variables: {
      ...variables,
      ...(objectId && { id: objectId, ids: [objectId] }),
    },
    context: {
      uri: CONFIG.GRAPHQL_URL(branch?.name),
    },
  });

  // Only show loading if we're actually loading something
  const loading = (!skip && queryConfig && (savedQueryLoading || pluginLoading)) || false;
  const error = savedQueryError || pluginError;

  // No-op refetch if query is not configured
  const safeRefetch = queryDocument
    ? () => {
        refetch();
      }
    : () => {};

  return {
    data: shouldSkipPluginQuery ? undefined : (pluginData as T | undefined),
    loading,
    error: error ? new Error(error.message) : undefined,
    refetch: safeRefetch,
  };
}
