import { Spinner } from "@infrahub/ui";
import { useState } from "react";

import type { PathTraversalResponse } from "../../domain/get-path-traversal";
import { copyAllPathsAsText, formatPathAsText, getKindCounts, pathPreview } from "../format-paths";
import { PathFlowGraph } from "../path-flow-graph";

type PathModeResultsProps = {
  data: PathTraversalResponse | undefined;
  isLoading: boolean;
  error: Error | null;
  selectedPath: number;
  onSelectPath: (index: number) => void;
  onExcludeKind: (kind: string) => void;
};

export function PathModeResults({
  data,
  isLoading,
  error,
  selectedPath,
  onSelectPath,
  onExcludeKind,
}: PathModeResultsProps) {
  const [copyFeedback, setCopyFeedback] = useState("");

  async function handleCopy(text: string) {
    await navigator.clipboard.writeText(text);
    setCopyFeedback("Copied!");
    setTimeout(() => setCopyFeedback(""), 2000);
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="max-w-md rounded-md border border-red-200 bg-red-50 p-4">
          <p className="text-red-700 text-sm">{error.message}</p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-gray-500">
        <Spinner />
        <span className="text-sm">Finding paths...</span>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex h-full items-center justify-center text-gray-300 text-sm">
        Select two objects and click "Find Paths"
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-gray-200 border-b p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="font-medium text-gray-700 text-sm">
            {data.total_paths_found} path{data.total_paths_found !== 1 ? "s" : ""} found
          </h3>
          {data.paths.length > 0 && (
            <button
              type="button"
              onClick={() => handleCopy(copyAllPathsAsText(data))}
              className="rounded px-2 py-0.5 text-blue-600 text-xs hover:bg-blue-50"
              title="Copy all paths to clipboard"
            >
              {copyFeedback || "Copy all"}
            </button>
          )}
        </div>

        {data.paths.length > 0 ? (
          <div className="space-y-1">
            {data.paths.map((path, index) => (
              <div
                key={index}
                className={`group flex items-start gap-1 rounded-md border p-2 transition-colors ${
                  selectedPath === index
                    ? "border-blue-300 bg-blue-50"
                    : "border-transparent hover:border-gray-200 hover:bg-gray-50"
                }`}
              >
                <button
                  type="button"
                  onClick={() => onSelectPath(index)}
                  className="min-w-0 flex-1 text-left"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={`font-medium text-xs ${
                        selectedPath === index ? "text-blue-700" : "text-gray-600"
                      }`}
                    >
                      Path {index + 1}
                    </span>
                    <span className="rounded-full bg-gray-200 px-1.5 py-0.5 text-[10px] text-gray-500">
                      {path.depth} hop{path.depth !== 1 ? "s" : ""}
                    </span>
                  </div>
                  <div className="mt-0.5 truncate text-[11px] text-gray-400">
                    {pathPreview(path)}
                  </div>
                  <div className="mt-0.5 truncate text-[10px] text-gray-300">
                    {getKindCounts(path)}
                  </div>
                </button>
                <button
                  type="button"
                  onClick={() => handleCopy(formatPathAsText(data, index))}
                  className="mt-0.5 flex-shrink-0 rounded p-0.5 text-gray-300 opacity-0 transition-opacity hover:text-gray-500 group-hover:opacity-100"
                  title="Copy this path"
                >
                  copy
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center text-gray-400 text-sm">No paths found</div>
        )}

        {data.paths[selectedPath] && (
          <div className="mt-3 rounded-md border border-gray-100 bg-gray-50 p-2 text-[11px] text-gray-600 leading-relaxed">
            {formatPathAsText(data, selectedPath)}
          </div>
        )}
      </div>

      {data.paths.length > 0 && (
        <div className="relative flex-1">
          <PathFlowGraph
            data={data}
            selectedPathIndex={selectedPath}
            onPathSelect={onSelectPath}
            onExcludeKind={onExcludeKind}
          />
        </div>
      )}
    </div>
  );
}
