import { DEFAULT_PLUGINS, GraphiQL } from "graphiql";
import { useQueryState } from "nuqs";

import { QSP } from "@/shared/config/qsp";
import { parallelModePlugin } from "@/shared/libs/graphiql/parallel-mode-plugin";
import { useGraphiqlTransport } from "@/shared/libs/graphiql/use-graphiql-transport";

import { useTheme } from "@/entities/config/ui/theme-provider";

import "graphiql/setup-workers/vite";
import "./graphiql-overrides.css";

const plugins = [...DEFAULT_PLUGINS, parallelModePlugin];

export function Component() {
  const [query] = useQueryState(QSP.QUERY);
  const transport = useGraphiqlTransport();
  const { resolvedTheme: theme } = useTheme();

  return (
    <GraphiQL
      className="relative rounded-2xl border"
      defaultEditorToolsVisibility
      initialQuery={query ?? undefined}
      plugins={plugins}
      forcedTheme={theme}
      transport={transport}
    />
  );
}
