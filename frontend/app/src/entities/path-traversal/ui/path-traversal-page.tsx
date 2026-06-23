import { Icon } from "@iconify-icon/react";
import { Button } from "@infrahub/ui";
import { parseAsStringLiteral, useQueryState } from "nuqs";
import { useState } from "react";

import { Tooltip } from "@/shared/components/aria/tooltip";
import Content from "@/shared/components/layout/content";

import { DependenciesModeMain } from "./dependencies-mode/dependencies-mode-main";
import { DependenciesModeSidebar } from "./dependencies-mode/dependencies-mode-sidebar";
import { PathModeMain } from "./path-mode/path-mode-main";
import { PathModeSidebar } from "./path-mode/path-mode-sidebar";

const MODES = ["path", "dependencies"] as const;
type Mode = (typeof MODES)[number];

const MODE_META: Record<Mode, { title: string; description: string; activeClass: string }> = {
  path: {
    title: "Path Traversal",
    description: "Find paths between two objects in the graph.",
    activeClass: "bg-blue-100 text-blue-700",
  },
  dependencies: {
    title: "Dependencies",
    description: "Find all connected objects of specific kinds.",
    activeClass: "bg-amber-100 text-amber-700",
  },
};

const MODE_LABELS: Record<Mode, string> = {
  path: "Path",
  dependencies: "Dependencies",
};

export function PathTraversalPage() {
  const [mode, setMode] = useQueryState(
    "mode",
    parseAsStringLiteral<Mode>(MODES as unknown as Mode[]).withDefault("path")
  );
  const [parametersOpen, setParametersOpen] = useState(true);

  function toggleParameters() {
    setParametersOpen((open) => !open);
  }

  const meta = MODE_META[mode];

  return (
    <div className="relative h-full overflow-hidden">
      <main className="absolute inset-0">
        {mode === "path" ? (
          <PathModeMain parametersOpen={parametersOpen} onParametersClick={toggleParameters} />
        ) : (
          <DependenciesModeMain
            parametersOpen={parametersOpen}
            onParametersClick={toggleParameters}
          />
        )}
      </main>

      {parametersOpen && (
        <Content.Card className="absolute top-4 right-4 bottom-4 z-10 flex w-80 flex-col overflow-hidden shadow-xl">
          <div className="border-gray-200 border-b p-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <h2 className="font-semibold text-lg">{meta.title}</h2>
                <p className="mt-1 text-gray-500 text-sm">{meta.description}</p>
              </div>
              <Tooltip message="Close panel">
                <Button
                  variant="ghost"
                  size="xs"
                  shape="square"
                  onPress={toggleParameters}
                  className="-mt-1 -mr-1 text-gray-400"
                >
                  <Icon icon="mdi:close" className="text-lg" />
                </Button>
              </Tooltip>
            </div>

            <div className="mt-2 flex gap-1">
              {MODES.map((m) => (
                <Button
                  key={m}
                  variant="ghost"
                  size="xs"
                  onPress={() => setMode(m)}
                  className={`flex-1 font-medium text-xs ${
                    mode === m ? MODE_META[m].activeClass : "text-gray-500"
                  }`}
                >
                  {MODE_LABELS[m]}
                </Button>
              ))}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto">
            {mode === "path" ? <PathModeSidebar /> : <DependenciesModeSidebar />}
          </div>
        </Content.Card>
      )}
    </div>
  );
}
