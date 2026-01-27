import { SlidersHorizontalIcon } from "lucide-react";
import React from "react";

import {
  getParallelQueryConfig,
  type ParallelQueryConfig,
  setParallelQueryConfig,
} from "@/shared/libs/graphiql/parallel-query-mode";

function ParallelModePlugin() {
  const [config, setConfig] = React.useState<ParallelQueryConfig>(getParallelQueryConfig);

  // Local state for input values to allow empty fields during editing
  const [pageSize, setPageSize] = React.useState(config.pageSize);
  const [maxConcurrent, setMaxConcurrent] = React.useState(config.maxConcurrent);
  const [delayMs, setDelayMs] = React.useState(config.delayMs);

  // Sync local state when config changes externally
  React.useEffect(() => {
    setPageSize(config.pageSize);
    setMaxConcurrent(config.maxConcurrent);
    setDelayMs(config.delayMs);
  }, [config.pageSize, config.maxConcurrent, config.delayMs]);

  const updateConfig = (partial: Partial<ParallelQueryConfig>) => {
    const next = setParallelQueryConfig(partial);
    setConfig(next);
  };

  const toggleEnabled = () => {
    updateConfig({ enabled: !config.enabled });
  };

  return (
    <div className="graphiql-doc-explorer-content p-4">
      <span className="rounded bg-amber-100 px-1.5 py-0.5 font-medium text-amber-800 text-xs">
        Alpha
      </span>
      <div className="graphiql-doc-explorer-title mb-4 flex items-center gap-2 font-semibold text-lg">
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
                  onChange={(e) => setPageSize(e.target.valueAsNumber)}
                  onBlur={() => {
                    if (!pageSize || pageSize < 1) {
                      updateConfig({ pageSize: 500 });
                      setPageSize(500);
                    } else if (pageSize > 10_000) {
                      updateConfig({ pageSize: 10_000 });
                      setPageSize(10_000);
                    } else {
                      updateConfig({ pageSize });
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
                  onChange={(e) => setMaxConcurrent(e.target.valueAsNumber)}
                  onBlur={() => {
                    if (!maxConcurrent || maxConcurrent < 1) {
                      updateConfig({ maxConcurrent: 5 });
                      setMaxConcurrent(5);
                    } else if (maxConcurrent > 50) {
                      updateConfig({ maxConcurrent: 50 });
                      setMaxConcurrent(50);
                    } else {
                      updateConfig({ maxConcurrent });
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
                  onChange={(e) => setDelayMs(e.target.valueAsNumber)}
                  onBlur={() => {
                    if (delayMs < 0 || Number.isNaN(delayMs)) {
                      updateConfig({ delayMs: 0 });
                      setDelayMs(0);
                    } else if (delayMs > 5000) {
                      updateConfig({ delayMs: 5000 });
                      setDelayMs(5000);
                    } else {
                      updateConfig({ delayMs });
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

export const parallelModePlugin = {
  title: "Parallel Mode",
  icon: SlidersHorizontalIcon,
  content: ParallelModePlugin,
};
