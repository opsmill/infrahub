import { Button, FloatingPanel } from "@infrahub/ui";
import { parseAsStringLiteral, useQueryState } from "nuqs";
import { useState } from "react";

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
        <FloatingPanel
          title={meta.title}
          description={meta.description}
          onClose={toggleParameters}
          className="absolute top-4 right-4 bottom-4 z-10 flex w-80 flex-col shadow-xl"
          headerContent={
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
          }
        >
          {mode === "path" ? <PathModeSidebar /> : <DependenciesModeSidebar />}
        </FloatingPanel>
      )}
    </div>
  );
}
