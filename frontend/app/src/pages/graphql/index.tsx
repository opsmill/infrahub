import { explorerPlugin } from "@graphiql/plugin-explorer";
import type { Fetcher } from "@graphiql/toolkit";
import { GraphiQL } from "graphiql";
import { useAtomValue } from "jotai";

import { CONFIG } from "@/config/config";
import { ACCESS_TOKEN_KEY } from "@/config/localStorage";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";

import { QSP } from "@/config/qsp";
import "@graphiql/plugin-explorer/dist/style.css";
import "graphiql/graphiql.min.css";
import { StringParam, useQueryParam } from "use-query-params";

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

  return (
    <GraphiQL
      defaultEditorToolsVisibility
      query={query ?? undefined}
      plugins={[explorerPlugin({ showAttribution: false })]}
      fetcher={fetcher(CONFIG.GRAPHQL_URL(branch?.name, waybackMachineDate))}
    />
  );
};

export function Component() {
  return <GraphqlSandboxPage />;
}
