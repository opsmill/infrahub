import {
  createTransport,
  type Transport,
  type TransportRequest,
  type TransportResponse,
} from "@graphiql/toolkit";
import { useAtomValue } from "jotai";

import { PRIORITY_HEADER, resolvePriority } from "@/shared/api/priority";
import { retryingFetch } from "@/shared/api/rate-limit/retrying-fetch";
import { queryClient } from "@/shared/api/rest/client";
import { CONFIG } from "@/shared/config/config";
import {
  type ParallelQueryConfig,
  parallelQueryConfigAtom,
} from "@/shared/libs/graphiql/parallel-query-mode";
import {
  analyzeQuery,
  generatePaginatedQueries,
  mergeResults,
} from "@/shared/libs/graphiql/parallel-query-utils";
import { store } from "@/shared/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { waitFor } from "@/shared/utils/common";

import { getAccessToken } from "@/entities/authentication/api/token-storage";
import { redirectToLogin } from "@/entities/authentication/domain/use-cases/redirect-to-login";
import { refreshAccessTokenQueryOptions } from "@/entities/authentication/ui/queries/refresh-access-token.query";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getObjectsCountFromApi } from "@/entities/nodes/object/api/get-objects-count-from-api";

export const sandboxFetch: typeof fetch = async (input, init) => {
  const headers = new Headers(init?.headers);
  // Sandbox bypasses our graphql client, so it must set priority here too.
  headers.set(PRIORITY_HEADER, resolvePriority(headers.get(PRIORITY_HEADER)));
  const send = () => retryingFetch(input, { ...init, headers });

  const accessToken = getAccessToken();
  // A token typed in the Headers tab is not the session's, so it is never refreshed.
  if (headers.has("authorization") || !accessToken) return send();

  headers.set("authorization", `Bearer ${accessToken}`);
  const response = await send();
  if (response.status !== 401) return response;

  const refreshed = await queryClient.query(refreshAccessTokenQueryOptions()).catch(() => null);
  if (!refreshed) {
    redirectToLogin();
    return response;
  }
  headers.set("authorization", `Bearer ${refreshed.access_token}`);
  return send();
};

// Parallel-mode settings are read at send time, so changing them keeps the transport and GraphiQL does not re-run introspection.
export function useGraphiqlTransport(): Transport {
  const { currentBranch } = useCurrentBranch();
  const waybackMachineDate = useAtomValue(datetimeAtom);
  const baseTransport = createTransport({
    url: CONFIG.GRAPHQL_URL(currentBranch.name, waybackMachineDate),
    fetch: sandboxFetch,
    supportedMethods: ["POST"],
    enableIncrementalDelivery: false,
  });
  // Only queries reach this, and with incremental delivery off the transport answers a query with one response.
  const sendOnce = (request: TransportRequest) =>
    baseTransport.send(request) as Promise<TransportResponse>;

  const sendInParallel = async (
    request: TransportRequest,
    parallelQueryConfig: ParallelQueryConfig,
    rootFieldName: string,
    hasCount: boolean
  ): Promise<TransportResponse> => {
    const startMs = performance.now();
    const { query } = request;

    const { data, errors } = await getObjectsCountFromApi({
      objectKind: rootFieldName,
      branchName: currentBranch.name,
      atDate: waybackMachineDate,
    });

    if (errors) {
      return sendOnce(request);
    }

    const totalCount: number = data?.[rootFieldName]?.count ?? 0;

    if (totalCount === 0) {
      const emptyResult: Record<string, unknown> = { edges: [] };
      if (hasCount) {
        emptyResult.count = 0;
      }
      return {
        ok: true,
        method: "POST",
        body: { data: { [rootFieldName]: emptyResult } },
        timing: { totalMs: performance.now() - startMs },
        size: {},
      };
    }

    const paginatedQueries = generatePaginatedQueries(
      query,
      rootFieldName,
      totalCount,
      parallelQueryConfig.pageSize
    );

    const responses: TransportResponse[] = [];
    const executing: Promise<void>[] = [];
    let pageIndex = 0;

    const executeNext = async (): Promise<void> => {
      const currentIndex = pageIndex;
      pageIndex += 1;
      if (currentIndex >= paginatedQueries.length) return;

      const paginatedQuery = paginatedQueries[currentIndex];
      if (!paginatedQuery) return;

      responses[currentIndex] = await sendOnce({ ...request, query: paginatedQuery });

      if (parallelQueryConfig.delayMs > 0 && pageIndex < paginatedQueries.length) {
        await waitFor(parallelQueryConfig.delayMs);
      }

      await executeNext();
    };

    for (let i = 0; i < Math.min(parallelQueryConfig.maxConcurrent, paginatedQueries.length); i++) {
      const startDelay = i * parallelQueryConfig.delayMs;
      if (startDelay > 0) {
        executing.push(waitFor(startDelay).then(executeNext));
      } else {
        executing.push(executeNext());
      }
    }

    await Promise.all(executing);

    const mergedData = mergeResults(
      responses.map((response) => response.body as { data: Record<string, unknown> }),
      rootFieldName,
      totalCount
    );

    // No single HTTP status describes several requests, so status and headers stay unset.
    return {
      ok: responses.every((response) => response.ok),
      method: "POST",
      body: { data: mergedData },
      timing: { totalMs: performance.now() - startMs },
      size: {
        request: responses.reduce((total, response) => total + (response.size.request ?? 0), 0),
        response: responses.reduce((total, response) => total + (response.size.response ?? 0), 0),
      },
    };
  };

  // Not async: a subscription comes back as a stream, which GraphiQL must receive as is.
  const send = (request: TransportRequest) => {
    const parallelQueryConfig = store.get(parallelQueryConfigAtom);
    if (!parallelQueryConfig.enabled || request.operationName === "IntrospectionQuery") {
      return baseTransport.send(request);
    }

    const { canParallelize, rootFieldName, hasCount } = analyzeQuery(request.query);
    if (!canParallelize || !rootFieldName) {
      return baseTransport.send(request);
    }

    return sendInParallel(request, parallelQueryConfig, rootFieldName, hasCount);
  };

  return {
    url: baseTransport.url,
    method: "POST",
    supportedMethods: ["POST"],
    send,
  };
}
