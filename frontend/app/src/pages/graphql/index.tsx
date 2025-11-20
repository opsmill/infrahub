import { explorerPlugin } from "@graphiql/plugin-explorer";
import type { Fetcher } from "@graphiql/toolkit";
import { GraphiQL, HISTORY_PLUGIN } from "graphiql";
import { useAtomValue } from "jotai";
import { useQueryState } from "nuqs";

import { CONFIG } from "@/config/config";
import { ACCESS_TOKEN_KEY } from "@/config/localStorage";
import { QSP } from "@/config/qsp";

import { datetimeAtom } from "@/shared/stores/time.atom";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";

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
  const [query] = useQueryState(QSP.QUERY);
  const { currentBranch } = useCurrentBranch();
  const waybackMachineDate = useAtomValue(datetimeAtom);

  return (
    <GraphiQL
      className="rounded-lg border border-gray-200"
      defaultEditorToolsVisibility
      initialQuery={query ?? undefined}
      plugins={plugins}
      forcedTheme="light"
      fetcher={fetcher(CONFIG.GRAPHQL_URL(currentBranch.name, waybackMachineDate))}
    />
  );
};

export function Component() {
  return <GraphqlSandboxPage />;
}
