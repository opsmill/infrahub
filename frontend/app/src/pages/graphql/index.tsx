import { explorerPlugin } from "@graphiql/plugin-explorer";
import type { Fetcher } from "@graphiql/toolkit";
import { GraphiQL, HISTORY_PLUGIN } from "graphiql";
import { useAtomValue } from "jotai";
import { useQueryState } from "nuqs";
import { useMemo } from "react";

import { CONFIG } from "@/shared/config/config";
import { QSP } from "@/shared/config/qsp";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";

import "graphiql/style.css";
import "@graphiql/plugin-explorer/style.css";

import {
  ParallelQueryProvider,
  useParallelQueryMode,
} from "@/shared/api/graphql/parallelQueryMode";
import { useParallelFetcher } from "@/shared/api/graphql/useParallelFetcher";

import { ACCESS_TOKEN_KEY } from "@/entities/authentication/constants";

import { parallelModePlugin } from "./parallel-mode-plugin";

// Plugins array is stable - parallelModePlugin reads config from context
const plugins = [HISTORY_PLUGIN, explorerPlugin(), parallelModePlugin];

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

const GraphqlSandboxPageContent = () => {
  const [query] = useQueryState(QSP.QUERY);
  const { currentBranch } = useCurrentBranch();
  const waybackMachineDate = useAtomValue(datetimeAtom);
  const { config } = useParallelQueryMode();

  // Memoize baseFetcher to prevent recreation on every render
  const baseFetcher = useMemo(
    () => createBaseFetcher(CONFIG.GRAPHQL_URL(currentBranch.name, waybackMachineDate)),
    [currentBranch.name, waybackMachineDate]
  );
  const { fetcher, loading, progress } = useParallelFetcher({ config, baseFetcher });

  return (
    <div className="flex h-full flex-col">
      {loading && progress.total > 0 && (
        <div className="flex items-center justify-center gap-2 border-gray-200 border-b bg-blue-50 px-3 py-2">
          <div className="h-2 w-32 overflow-hidden rounded-full bg-gray-200">
            <div
              className="h-full bg-blue-500 transition-all duration-200"
              style={{ width: `${Math.round((progress.completed / progress.total) * 100)}%` }}
            />
          </div>
          <span className="text-blue-700 text-sm">
            Parallel mode: {progress.completed}/{progress.total} pages
          </span>
        </div>
      )}
      <GraphiQL
        className="flex-1 rounded-lg border border-gray-200"
        defaultEditorToolsVisibility
        initialQuery={query ?? undefined}
        plugins={plugins}
        forcedTheme="light"
        fetcher={fetcher}
      />
    </div>
  );
};

const GraphqlSandboxPage = () => {
  return (
    <ParallelQueryProvider>
      <GraphqlSandboxPageContent />
    </ParallelQueryProvider>
  );
};

export function Component() {
  return <GraphqlSandboxPage />;
}
