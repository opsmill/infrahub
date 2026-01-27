import type { Fetcher } from "@graphiql/toolkit";
import { useAtomValue } from "jotai";

import { CONFIG } from "@/shared/config/config";
import { getParallelQueryConfig } from "@/shared/libs/graphiql/parallel-query-mode";
import {
  analyzeQuery,
  generatePaginatedQueries,
  mergeResults,
} from "@/shared/libs/graphiql/parallel-query-utils";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { waitFor } from "@/shared/utils/common";

import { ACCESS_TOKEN_KEY } from "@/entities/authentication/constants";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getObjectsCountFromApi } from "@/entities/nodes/object/api/get-objects-count-from-api";

const createBaseFetcher =
  (url: string): Fetcher =>
  async (graphQLParams) => {
    const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
    const data = await fetch(url, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...(accessToken && {
          authorization: `Bearer ${accessToken}`,
        }),
      },
      body: JSON.stringify(graphQLParams),
      credentials: "same-origin",
    });
    return data.json().catch(() => data.text());
  };

/**
 * The fetcher reads config from localStorage at call time to avoid
 * re-creating the fetcher reference when config changes. This prevents
 * GraphiQL from re-running IntrospectionQuery on config toggle.
 */
export function useGraphiqlFetcher(): Fetcher {
  const { currentBranch } = useCurrentBranch();
  const waybackMachineDate = useAtomValue(datetimeAtom);
  const baseFetcher = createBaseFetcher(CONFIG.GRAPHQL_URL(currentBranch.name, waybackMachineDate));

  return async (graphQLParams, opts) => {
    const parallelQueryConfig = getParallelQueryConfig();

    if (!parallelQueryConfig.enabled || graphQLParams.operationName === "IntrospectionQuery") {
      return baseFetcher(graphQLParams, opts);
    }

    const { query } = graphQLParams;
    const queryInfo = analyzeQuery(query);

    // If query already uses pagination or can't be parallelized, use base fetcher
    if (!queryInfo.canParallelize || !queryInfo.rootFieldName) {
      return baseFetcher(graphQLParams, opts);
    }

    // Step 1: Execute count query
    const { data, errors } = await getObjectsCountFromApi({
      objectKind: queryInfo.rootFieldName,
      branchName: currentBranch.name,
      atDate: waybackMachineDate,
    });

    if (errors) {
      return baseFetcher(graphQLParams, opts);
    }

    const totalCount: number = data?.[queryInfo.rootFieldName]?.count ?? 0;

    if (totalCount === 0) {
      const emptyResult: Record<string, unknown> = { edges: [] };
      // Only include count if the original query requested it
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
      parallelQueryConfig.pageSize
    );

    // Step 3: Execute queries with concurrency limit
    const results: Array<{ data: Record<string, unknown> }> = [];
    const executing: Promise<void>[] = [];
    let pageIndex = 0;

    const executeNext = async (): Promise<void> => {
      const currentIndex = pageIndex;
      pageIndex += 1;
      if (currentIndex >= paginatedQueries.length) return;

      const paginatedQuery = paginatedQueries[currentIndex];
      if (!paginatedQuery) return;

      results[currentIndex] = (await baseFetcher(
        { ...graphQLParams, query: paginatedQuery },
        opts
      )) as {
        data: Record<string, unknown>;
      };

      // Add waitFor before starting next query in this lane
      if (parallelQueryConfig.delayMs > 0 && pageIndex < paginatedQueries.length) {
        await waitFor(parallelQueryConfig.delayMs);
      }

      // Start next query if there are more
      await executeNext();
    };

    // Start up to maxConcurrent parallel executions with staggered initial delays
    for (let i = 0; i < Math.min(parallelQueryConfig.maxConcurrent, paginatedQueries.length); i++) {
      const startDelay = i * parallelQueryConfig.delayMs;
      if (startDelay > 0) {
        executing.push(waitFor(startDelay).then(executeNext));
      } else {
        executing.push(executeNext());
      }
    }

    await Promise.all(executing);

    // Step 4: Merge results
    const mergedData = mergeResults(results, queryInfo.rootFieldName, totalCount);

    return { data: mergedData };
  };
}
