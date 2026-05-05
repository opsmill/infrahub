import { parseAsStringEnum, useQueryState } from "nuqs";
import { useState } from "react";

import { DependenciesModeMain } from "./dependencies-mode/dependencies-mode-main";
import { DependenciesModeSidebar } from "./dependencies-mode/dependencies-mode-sidebar";
import { PathModeMain } from "./path-mode/path-mode-main";
import { PathModeSidebar } from "./path-mode/path-mode-sidebar";

const MODES = ["path", "dependencies"] as const;
type Mode = (typeof MODES)[number];

export function PathTraversalPage() {
  const [mode, setMode] = useQueryState(
    "mode",
    parseAsStringEnum<Mode>(MODES as unknown as Mode[]).withDefault("path")
  );
  const [isPanelCollapsed, setIsPanelCollapsed] = useState(false);

  return (
    <div className="flex h-full overflow-hidden">
      <div
        className={`flex-shrink-0 overflow-y-auto border-gray-200 border-r transition-all duration-300 ${
          isPanelCollapsed ? "w-3" : "w-80"
        }`}
      >
        {isPanelCollapsed ? (
          <button
            type="button"
            onClick={() => setIsPanelCollapsed(false)}
            className="flex h-full w-full items-center justify-center bg-gray-50 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
            title="Expand panel"
          >
            ›
          </button>
        ) : (
          <>
            <div className="border-gray-200 border-b p-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="font-semibold text-lg">
                    {mode === "path" ? "Path Traversal" : "Dependencies"}
                  </h2>
                  <p className="mt-1 text-gray-500 text-sm">
                    {mode === "path"
                      ? "Find paths between two objects in the graph."
                      : "Find all connected objects of specific kinds."}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setIsPanelCollapsed(true)}
                  className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                  title="Collapse panel"
                >
                  ‹
                </button>
              </div>

              <div className="mt-2 flex gap-1">
                <button
                  type="button"
                  onClick={() => setMode("path")}
                  className={`flex-1 rounded px-2 py-1 font-medium text-xs ${
                    mode === "path"
                      ? "bg-blue-100 text-blue-700"
                      : "text-gray-500 hover:bg-gray-100"
                  }`}
                >
                  Path
                </button>
                <button
                  type="button"
                  onClick={() => setMode("dependencies")}
                  className={`flex-1 rounded px-2 py-1 font-medium text-xs ${
                    mode === "dependencies"
                      ? "bg-amber-100 text-amber-700"
                      : "text-gray-500 hover:bg-gray-100"
                  }`}
                >
                  Dependencies
                </button>
              </div>
            </div>

            {mode === "path" ? <PathModeSidebar /> : <DependenciesModeSidebar />}
          </>
        )}
      </div>

      <main className="relative flex-1 overflow-hidden">
        {mode === "path" ? <PathModeMain /> : <DependenciesModeMain />}
      </main>
    </div>
  );
}
