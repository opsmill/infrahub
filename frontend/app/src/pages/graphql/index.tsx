import { explorerPlugin } from "@graphiql/plugin-explorer";
import { GraphiQL, HISTORY_PLUGIN } from "graphiql";
import { useQueryState } from "nuqs";

import { QSP } from "@/shared/config/qsp";
import { parallelModePlugin } from "@/shared/libs/graphiql/parallel-mode-plugin";
import { useGraphiqlFetcher } from "@/shared/libs/graphiql/use-graphiql-fetcher";

import "graphiql/style.css";
import "@graphiql/plugin-explorer/style.css";

const plugins = [HISTORY_PLUGIN, explorerPlugin(), parallelModePlugin];

export function Component() {
  const [query] = useQueryState(QSP.QUERY);
  const fetcher = useGraphiqlFetcher();

  return (
    <GraphiQL
      className="rounded-lg border border-gray-200"
      defaultEditorToolsVisibility
      initialQuery={query ?? undefined}
      plugins={plugins}
      forcedTheme="light"
      fetcher={fetcher}
    />
  );
}
