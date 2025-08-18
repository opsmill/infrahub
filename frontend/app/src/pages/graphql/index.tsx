import { CONFIG } from "@/config/config";
import { ACCESS_TOKEN_KEY } from "@/config/localStorage";
import { QSP } from "@/config/qsp";
import { currentBranchAtom } from "@/entities/branches/stores";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { explorerPlugin } from "@graphiql/plugin-explorer";
import type { Fetcher } from "@graphiql/toolkit";
import { GraphiQL, HISTORY_PLUGIN } from "graphiql";
import { useAtomValue } from "jotai";
import { StringParam, useQueryParam } from "use-query-params";

import GraphQLWorker from "@/vendor/monaco-graphql/graphql.worker?worker";
// Bundle Monaco workers locally so build works offline and avoids dep pre-bundling issues
// with ?worker imports inside node_modules.
import EditorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";
import JsonWorker from "monaco-editor/esm/vs/language/json/json.worker?worker";
import "graphiql/style.css";
import "@graphiql/plugin-explorer/style.css";

const plugins = [HISTORY_PLUGIN, explorerPlugin()];

const fetcher =
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

const GraphqlSandboxPage = () => {
  const [query] = useQueryParam(QSP.QUERY, StringParam);
  const branch = useAtomValue(currentBranchAtom);
  const waybackMachineDate = useAtomValue(datetimeAtom);

  // Ensure Monaco workers are available when running offline
  (globalThis as any).MonacoEnvironment = {
    getWorker(_workerId: unknown, label: string) {
      switch (label) {
        case "json":
          return new (JsonWorker as unknown as { new (): Worker })();
        case "graphql":
          return new (GraphQLWorker as unknown as { new (): Worker })();
        default:
          return new (EditorWorker as unknown as { new (): Worker })();
      }
    },
  };

  return (
    <GraphiQL
      className="rounded-lg border border-gray-200"
      defaultEditorToolsVisibility
      initialQuery={query ?? undefined}
      plugins={plugins}
      forcedTheme="light"
      fetcher={fetcher(CONFIG.GRAPHQL_URL(branch?.name, waybackMachineDate))}
    />
  );
};

export function Component() {
  return <GraphqlSandboxPage />;
}
