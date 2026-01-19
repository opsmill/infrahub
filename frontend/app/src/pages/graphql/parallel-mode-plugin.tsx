import { useEffect, useState } from "react";

import { useParallelQueryMode } from "@/shared/api/graphql/parallelQueryMode";

/**
 * Content component for the parallel mode plugin.
 * Uses the context hook directly to avoid re-creating the plugin on config changes.
 */
function ParallelModePluginContent() {
  const { config, toggleEnabled, setConfig } = useParallelQueryMode();

  // Local state for input values to allow empty fields during editing
  const [pageSize, setPageSize] = useState(String(config.pageSize));
  const [maxConcurrent, setMaxConcurrent] = useState(String(config.maxConcurrent));
  const [delayMs, setDelayMs] = useState(String(config.delayMs));

  // Sync local state when config changes externally
  useEffect(() => {
    setPageSize(String(config.pageSize));
    setMaxConcurrent(String(config.maxConcurrent));
    setDelayMs(String(config.delayMs));
  }, [config.pageSize, config.maxConcurrent, config.delayMs]);

  return (
    <div className="graphiql-doc-explorer-content p-4">
      <div className="graphiql-doc-explorer-title mb-4 font-semibold text-lg">
        Parallel Mode Settings
      </div>
      <p className="mb-4 text-gray-600 text-sm">
        When enabled, queries without <code>offset</code> or <code>limit</code> arguments will be
        automatically paginated and executed in parallel for better performance on large datasets.
      </p>

      <div className="mb-6 space-y-4">
        <label className="flex cursor-pointer items-center gap-3">
          <input
            type="checkbox"
            checked={config.enabled}
            onChange={toggleEnabled}
            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <span className="font-medium text-sm">Enable Parallel Mode</span>
        </label>

        {config.enabled && (
          <div className="space-y-4 border-gray-200 border-l-2 pl-4">
            <div>
              <label className="mb-1 block font-medium text-gray-700 text-sm">
                Page Size
                <input
                  type="number"
                  value={pageSize}
                  onChange={(e) => setPageSize(e.target.value)}
                  onBlur={() => {
                    const value = Number(pageSize);
                    if (!value || value < 1) {
                      setConfig({ pageSize: 500 });
                      setPageSize("500");
                    } else if (value > 10_000) {
                      setConfig({ pageSize: 10_000 });
                      setPageSize("10000");
                    } else {
                      setConfig({ pageSize: value });
                    }
                  }}
                  className="mt-1 block w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  min={1}
                  max={10_000}
                />
              </label>
              <p className="mt-1 text-gray-500 text-xs">Number of items per page (default: 500)</p>
            </div>

            <div>
              <label className="mb-1 block font-medium text-gray-700 text-sm">
                Max Concurrent Requests
                <input
                  type="number"
                  value={maxConcurrent}
                  onChange={(e) => setMaxConcurrent(e.target.value)}
                  onBlur={() => {
                    const value = Number(maxConcurrent);
                    if (!value || value < 1) {
                      setConfig({ maxConcurrent: 5 });
                      setMaxConcurrent("5");
                    } else if (value > 50) {
                      setConfig({ maxConcurrent: 50 });
                      setMaxConcurrent("50");
                    } else {
                      setConfig({ maxConcurrent: value });
                    }
                  }}
                  className="mt-1 block w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  min={1}
                  max={50}
                />
              </label>
              <p className="mt-1 text-gray-500 text-xs">
                Maximum parallel requests (default: 5, max: 50)
              </p>
            </div>

            <div>
              <label className="mb-1 block font-medium text-gray-700 text-sm">
                Delay Between Queries (ms)
                <input
                  type="number"
                  value={delayMs}
                  onChange={(e) => setDelayMs(e.target.value)}
                  onBlur={() => {
                    const value = Number(delayMs);
                    if (value < 0 || Number.isNaN(value) || delayMs === "") {
                      setConfig({ delayMs: 0 });
                      setDelayMs("0");
                    } else if (value > 5000) {
                      setConfig({ delayMs: 5000 });
                      setDelayMs("5000");
                    } else {
                      setConfig({ delayMs: value });
                    }
                  }}
                  className="mt-1 block w-full rounded border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  min={0}
                  max={5000}
                />
              </label>
              <p className="mt-1 text-gray-500 text-xs">
                Delay between each query in milliseconds (default: disabled)
              </p>
            </div>
          </div>
        )}
      </div>

      <div className="border-gray-200 border-t pt-4">
        <div className="font-medium text-gray-700 text-sm">How it works:</div>
        <ol className="mt-2 list-inside list-decimal space-y-1 text-gray-600 text-xs">
          <li>Executes a count query to determine total items</li>
          <li>Splits into multiple paginated queries</li>
          <li>Executes queries in parallel batches</li>
          <li>Merges results into a single response</li>
        </ol>
      </div>
    </div>
  );
}

/**
 * Creates a GraphiQL plugin for configuring parallel query mode.
 * This appears as a settings icon in the GraphiQL sidebar.
 * The plugin is stable and doesn't need to be recreated when config changes.
 */
export const parallelModePlugin = {
  title: "Parallel Mode Settings",
  icon: () => (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="graphiql-toolbar-icon"
    >
      {/* Parallel lines icon */}
      <line x1="4" y1="6" x2="20" y2="6" />
      <line x1="4" y1="12" x2="20" y2="12" />
      <line x1="4" y1="18" x2="20" y2="18" />
      <circle cx="18" cy="6" r="2" fill="currentColor" />
      <circle cx="10" cy="12" r="2" fill="currentColor" />
      <circle cx="14" cy="18" r="2" fill="currentColor" />
    </svg>
  ),
  content: ParallelModePluginContent,
};
