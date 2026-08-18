import { explorerPlugin } from "@graphiql/plugin-explorer";
import { useResolvedTheme } from "@infrahub/ui";
import { GraphiQL, HISTORY_PLUGIN } from "graphiql";
import { useQueryState } from "nuqs";

import { QSP } from "@/shared/config/qsp";
import { parallelModePlugin } from "@/shared/libs/graphiql/parallel-mode-plugin";
import { useGraphiqlFetcher } from "@/shared/libs/graphiql/use-graphiql-fetcher";

import "graphiql/style.css";
import "@graphiql/plugin-explorer/style.css";
import "./graphiql-overrides.css";

const plugins = [HISTORY_PLUGIN, explorerPlugin(), parallelModePlugin];

export function Component() {
  const [query] = useQueryState(QSP.QUERY);
  const fetcher = useGraphiqlFetcher();
  // Forcing the resolved palette rather than "system" keeps the sandbox from running its own
  // prefers-color-scheme check, which could disagree with the app around it. It also hides
  // GraphiQL's own theme picker, leaving one place to change the theme.
  const theme = useResolvedTheme();

  return (
    <GraphiQL
      className="rounded-lg border"
      defaultEditorToolsVisibility
      initialQuery={query ?? undefined}
      plugins={plugins}
      forcedTheme={theme}
      fetcher={fetcher}
    />
  );
}
