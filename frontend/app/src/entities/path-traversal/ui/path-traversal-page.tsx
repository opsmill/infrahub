import { Icon } from "@iconify-icon/react";
import { parseAsStringEnum, useQueryState } from "nuqs";
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
    parseAsStringEnum<Mode>(MODES as unknown as Mode[]).withDefault("path")
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
        <aside className="absolute top-4 right-4 bottom-4 z-10 flex w-80 flex-col overflow-hidden rounded-lg border border-gray-200 bg-white shadow-xl">
          <div className="border-gray-200 border-b p-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <h2 className="font-semibold text-lg">{meta.title}</h2>
                <p className="mt-1 text-gray-500 text-sm">{meta.description}</p>
              </div>
              <button
                type="button"
                onClick={toggleParameters}
                className="-mt-1 -mr-1 flex h-7 w-7 shrink-0 items-center justify-center rounded text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                title="Close panel"
              >
                <Icon icon="mdi:close" className="text-lg" />
              </button>
            </div>

            <div className="mt-2 flex gap-1">
              {MODES.map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMode(m)}
                  className={`flex-1 rounded px-2 py-1 font-medium text-xs ${
                    mode === m ? MODE_META[m].activeClass : "text-gray-500 hover:bg-gray-100"
                  }`}
                >
                  {MODE_LABELS[m]}
                </button>
              ))}
            </div>
          </div>

          <div className="flex-1 overflow-y-auto">
            {mode === "path" ? <PathModeSidebar /> : <DependenciesModeSidebar />}
          </div>
        </aside>
      )}
    </div>
  );
}
