import type { Fetcher, FetcherParams } from "@graphiql/toolkit";
import { useCallback, useRef, useState } from "react";

import type { ParallelQueryConfig } from "./parallelQueryMode";
import {
  analyzeQuery,
  generateCountQuery,
  generatePaginatedQueries,
  mergeResults,
} from "./parallelQueryUtils";

interface ParallelQueryProgress {
  completed: number;
  total: number;
}

interface ParallelQueryState {
  loading: boolean;
  progress: ParallelQueryProgress;
  error: Error | null;
}

interface UseParallelFetcherOptions {
  config: ParallelQueryConfig;
  baseFetcher: Fetcher;
}

/**
 * Hook that wraps a GraphiQL fetcher to add parallel query support.
 * When parallel mode is enabled and a query doesn't use offset/limit,
 * it will automatically paginate the query and merge results.
 */
export function useParallelFetcher({ config, baseFetcher }: UseParallelFetcherOptions) {
  const [state, setState] = useState<ParallelQueryState>({
    loading: false,
    progress: { completed: 0, total: 0 },
    error: null,
  });

  // Use refs to avoid recreating the fetcher callback when config/baseFetcher change
  const configRef = useRef(config);
  const baseFetcherRef = useRef(baseFetcher);
  configRef.current = config;
  baseFetcherRef.current = baseFetcher;

  const parallelFetcher: Fetcher = useCallback(async (graphQLParams: FetcherParams, opts) => {
    const query = graphQLParams.query;
    const currentConfig = configRef.current;
    const currentBaseFetcher = baseFetcherRef.current;

    // If no query or parallel mode disabled, use base fetcher
    if (!query || !currentConfig.enabled) {
      return currentBaseFetcher(graphQLParams, opts);
    }

    const queryInfo = analyzeQuery(query);

    // If query already uses pagination or can't be parallelized, use base fetcher
    if (!queryInfo.canParallelize || !queryInfo.rootFieldName) {
      return currentBaseFetcher(graphQLParams, opts);
    }

    setState({ loading: true, progress: { completed: 0, total: 0 }, error: null });

    try {
      // Step 1: Execute count query
      const countQuery = generateCountQuery(query, queryInfo.rootFieldName);
      const countResult = (await currentBaseFetcher(
        { ...graphQLParams, query: countQuery },
        opts
      )) as {
        data?: Record<string, { count?: number }>;
      };

      const totalCount = countResult.data?.[queryInfo.rootFieldName]?.count ?? 0;

      if (totalCount === 0) {
        setState({ loading: false, progress: { completed: 0, total: 0 }, error: null });
        // Only include count if the original query requested it
        const emptyResult: Record<string, unknown> = { edges: [] };
        if (queryInfo.hasCount) {
          emptyResult.count = 0;
        }
        return { data: { [queryInfo.rootFieldName]: emptyResult } };
      }

      // Step 2: Generate paginated queries
      const paginatedQueries = generatePaginatedQueries(
        query,
        queryInfo.rootFieldName,
        totalCount,
        currentConfig.pageSize
      );

      const totalPages = paginatedQueries.length;
      setState((s) => ({ ...s, progress: { completed: 0, total: totalPages } }));

      // Step 3: Execute queries with concurrency limit
      const results: Array<{ data: Record<string, unknown> }> = [];
      const executing: Promise<void>[] = [];
      let pageIndex = 0;

      // Helper to add delay
      const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

      const executeNext = async (): Promise<void> => {
        const currentIndex = pageIndex;
        pageIndex += 1;
        if (currentIndex >= paginatedQueries.length) return;

        const paginatedQuery = paginatedQueries[currentIndex];
        if (!paginatedQuery) return;

        const result = (await currentBaseFetcher(
          { ...graphQLParams, query: paginatedQuery },
          opts
        )) as {
          data: Record<string, unknown>;
        };

        results[currentIndex] = result;
        setState((s) => ({
          ...s,
          progress: { ...s.progress, completed: s.progress.completed + 1 },
        }));

        // Add delay before starting next query in this lane
        if (currentConfig.delayMs > 0 && pageIndex < paginatedQueries.length) {
          await delay(currentConfig.delayMs);
        }

        // Start next query if there are more
        await executeNext();
      };

      // Start up to maxConcurrent parallel executions with staggered initial delays
      for (let i = 0; i < Math.min(currentConfig.maxConcurrent, paginatedQueries.length); i++) {
        const startDelay = i * currentConfig.delayMs;
        if (startDelay > 0) {
          executing.push(delay(startDelay).then(executeNext));
        } else {
          executing.push(executeNext());
        }
      }

      await Promise.all(executing);

      // Step 4: Merge results
      const mergedData = mergeResults(results, queryInfo.rootFieldName, totalCount);

      setState({
        loading: false,
        progress: { completed: totalPages, total: totalPages },
        error: null,
      });

      return { data: mergedData };
    } catch (error) {
      const err = error instanceof Error ? error : new Error(String(error));
      setState({ loading: false, progress: { completed: 0, total: 0 }, error: err });
      throw error;
    }
  }, []); // Empty deps - we use refs to access current values

  return {
    fetcher: parallelFetcher,
    ...state,
  };
}
