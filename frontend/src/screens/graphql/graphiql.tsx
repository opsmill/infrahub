import React from "react";
import { GraphiQL } from "graphiql";
import { explorerPlugin } from "@graphiql/plugin-explorer";
import type { Fetcher } from "@graphiql/toolkit";
import { useAtomValue } from "jotai/index";

import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { CONFIG } from "../../config/config";
import { ACCESS_TOKEN_KEY } from "../../config/constants";
import { datetimeAtom } from "../../state/atoms/time.atom";

import "graphiql/graphiql.min.css";
import "@graphiql/plugin-explorer/dist/style.css";

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

const GraphiQLPage = () => {
  const branch = useAtomValue(currentBranchAtom);
  const waybackMachineDate = useAtomValue(datetimeAtom);

  return (
    <GraphiQL
      defaultEditorToolsVisibility
      plugins={[explorerPlugin({ showAttribution: false })]}
      fetcher={fetcher(CONFIG.GRAPHQL_URL(branch?.name, waybackMachineDate))}
    />
  );
};

export default GraphiQLPage;
