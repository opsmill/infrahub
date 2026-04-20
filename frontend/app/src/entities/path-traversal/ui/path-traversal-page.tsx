import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router";

import { Spinner } from "@/shared/components/ui/spinner";

import type { PathResult, PathTraversalResponse } from "../domain/get-path-traversal";
import type { ReachableNodesResponse } from "../domain/get-reachable-nodes";
import { useGetPathTraversal } from "../domain/path-traversal.query";
import { useGetReachableNodes } from "../domain/reachable-nodes.query";
import { DependencySelector } from "./dependency-selector";
import { NodeSelector } from "./node-selector";
import { PathFlowGraph } from "./path-flow-graph";
import { formatRelName, getKindColor } from "./utils";

function formatPathAsText(data: PathTraversalResponse, pathIndex: number): string {
  const path = data.paths[pathIndex];
  if (!path) return "";
  const nodeLabels = path.nodes.map((n) => n.display_label);
  const parts: string[] = [];
  for (let i = 0; i < nodeLabels.length; i++) {
    parts.push(nodeLabels[i] ?? "");
    if (i < nodeLabels.length - 1) {
      const rel = path.relationships[i];
      if (rel) {
        parts.push(`-[${formatRelName(rel.name)}]->`);
      } else {
        parts.push(" -> ");
      }
    }
  }
  return parts.join(" ");
}

function copyAllPathsAsText(data: PathTraversalResponse): string {
  return data.paths
    .map((path, i) => `Path ${i + 1}: ${path.nodes.map((n) => n.display_label).join(" → ")}`)
    .join("\n");
}

function pathPreview(path: PathResult, maxNodes: number = 3): string {
  const names = path.nodes.map((n) => n.display_label);
  if (names.length <= maxNodes) return names.join(" -> ");
  const first = names[0];
  const last = names.at(-1);
  return `${first} -> ... -> ${last}`;
}

function getKindCounts(path: PathResult): string {
  const counts = new Map<string, number>();
  for (const node of path.nodes) {
    counts.set(node.kind, (counts.get(node.kind) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([kind, count]) => `${count}x ${kind}`)
    .join(", ");
}

function reachableNodesToPathResponse(reachable: ReachableNodesResponse): PathTraversalResponse {
  // Use the first reachable node as a synthetic "destination" for the graph
  const firstNode = reachable.reachable_nodes[0];
  const destination = firstNode
    ? { id: firstNode.id, kind: firstNode.kind, display_label: firstNode.display_label }
    : reachable.source;

  return {
    paths: reachable.paths,
    source: reachable.source,
    destination,
    total_paths_found: reachable.paths.length,
  };
}

export function PathTraversalPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialSourceId = searchParams.get("source") ?? "";
  const initialDestinationId = searchParams.get("destination") ?? "";
  const initialDepth = Number(searchParams.get("depth")) || 5;
  const initialMaxPaths = Number(searchParams.get("maxPaths")) || 10;
  const initialSelectedPath = Number(searchParams.get("selectedPath")) || 0;
  const initialMode = (searchParams.get("mode") as "path" | "impact") || "path";

  // Mode toggle
  const [mode, setMode] = useState<"path" | "impact">(initialMode);

  // Path traversal state
  const [sourceId, setSourceId] = useState(initialSourceId);
  const [destinationId, setDestinationId] = useState(initialDestinationId);
  const [maxDepth, setMaxDepth] = useState(initialDepth);
  const [maxPaths, setMaxPaths] = useState(initialMaxPaths);
  const [kindFilter, setKindFilter] = useState<string[]>([]);
  const [excludedKinds, setExcludedKinds] = useState<string[]>([]);
  const [selectedPathIndex, setSelectedPathIndex] = useState(initialSelectedPath);
  const [queryEnabled, setQueryEnabled] = useState(!!initialSourceId && !!initialDestinationId);
  const [copyFeedback, setCopyFeedback] = useState("");
  const [isPanelCollapsed, setIsPanelCollapsed] = useState(false);

  // Dependencies state
  const [depsSourceId, setDepsSourceId] = useState("");
  const [depsTargetKinds, setDepsTargetKinds] = useState<string[]>([]);
  const [depsMaxDepth, setDepsMaxDepth] = useState(5);
  const [depsQueryEnabled, setDepsQueryEnabled] = useState(false);

  const { data, isLoading, error } = useGetPathTraversal(
    { sourceId, destinationId, maxDepth, maxPaths, kindFilter, excludedKinds },
    { enabled: mode === "path" && queryEnabled && !!sourceId && !!destinationId }
  );

  const {
    data: depsData,
    isLoading: depsLoading,
    error: depsError,
  } = useGetReachableNodes(
    { sourceId: depsSourceId, targetKinds: depsTargetKinds, maxDepth: depsMaxDepth },
    {
      enabled:
        mode === "impact" && depsQueryEnabled && !!depsSourceId && depsTargetKinds.length > 0,
    }
  );

  const updateSearchParams = useCallback(
    (updates: Record<string, string>) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          for (const [key, value] of Object.entries(updates)) {
            if (value) {
              next.set(key, value);
            } else {
              next.delete(key);
            }
          }
          return next;
        },
        { replace: true }
      );
    },
    [setSearchParams]
  );

  function handleModeChange(newMode: "path" | "impact") {
    setMode(newMode);
    updateSearchParams({ mode: newMode });
  }

  function handleSearch(params: {
    sourceId: string;
    destinationId: string;
    maxDepth: number;
    maxPaths: number;
    kindFilter: string[];
    excludedKinds: string[];
  }) {
    setSourceId(params.sourceId);
    setDestinationId(params.destinationId);
    setMaxDepth(params.maxDepth);
    setMaxPaths(params.maxPaths);
    setKindFilter(params.kindFilter);
    setExcludedKinds(params.excludedKinds);
    setSelectedPathIndex(0);
    setQueryEnabled(true);
    updateSearchParams({
      source: params.sourceId,
      destination: params.destinationId,
      depth: String(params.maxDepth),
      maxPaths: String(params.maxPaths),
      selectedPath: "0",
    });
  }

  function handleDepsSearch(params: { sourceId: string; targetKinds: string[]; maxDepth: number }) {
    setDepsSourceId(params.sourceId);
    setDepsTargetKinds(params.targetKinds);
    setDepsMaxDepth(params.maxDepth);
    setDepsQueryEnabled(true);
  }

  function handleSelectPath(index: number) {
    setSelectedPathIndex(index);
    updateSearchParams({ selectedPath: String(index) });
  }

  // Keyboard shortcuts
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Don't intercept when typing in inputs
      const tag = (e.target as HTMLElement).tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;

      // 1-9 to switch paths (only in path mode)
      if (mode === "path" && data && e.key >= "1" && e.key <= "9") {
        const index = Number.parseInt(e.key, 10) - 1;
        if (index < data.paths.length) {
          handleSelectPath(index);
        }
      }

      // Arrow up/down to navigate paths
      const totalPaths =
        mode === "path" ? (data?.paths.length ?? 0) : (depsData?.reachable_nodes.length ?? 0);
      if (totalPaths > 0 && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
        e.preventDefault();
        const next =
          e.key === "ArrowDown"
            ? Math.min(selectedPathIndex + 1, totalPaths - 1)
            : Math.max(selectedPathIndex - 1, 0);
        handleSelectPath(next);
      }

      // Escape to clear query
      if (e.key === "Escape") {
        if (mode === "path") {
          setQueryEnabled(false);
        } else {
          setDepsQueryEnabled(false);
        }
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [data, depsData, mode, selectedPathIndex]);

  async function handleCopyPath(text: string) {
    await navigator.clipboard.writeText(text);
    setCopyFeedback("Copied!");
    setTimeout(() => setCopyFeedback(""), 2000);
  }

  const activeError = mode === "path" ? error : depsError;
  const activeLoading = mode === "path" ? isLoading : depsLoading;
  const activeQueryEnabled = mode === "path" ? queryEnabled : depsQueryEnabled;

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left panel: selector */}
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
            <svg
              className="size-3"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
            </svg>
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
                      ? "Find paths between two nodes in the graph."
                      : "Find all connected nodes of specific kinds."}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setIsPanelCollapsed(true)}
                  className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
                  title="Collapse panel"
                >
                  <svg
                    className="size-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
                  </svg>
                </button>
              </div>

              {/* Mode toggle */}
              <div className="mt-2 flex gap-1">
                <button
                  type="button"
                  onClick={() => handleModeChange("path")}
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
                  onClick={() => handleModeChange("impact")}
                  className={`flex-1 rounded px-2 py-1 font-medium text-xs ${
                    mode === "impact"
                      ? "bg-amber-100 text-amber-700"
                      : "text-gray-500 hover:bg-gray-100"
                  }`}
                >
                  Dependencies
                </button>
              </div>
            </div>

            {mode === "path" && (
              <>
                <NodeSelector
                  onSearch={handleSearch}
                  isLoading={isLoading}
                  initialSourceId={initialSourceId}
                  initialDestinationId={initialDestinationId}
                  maxDepth={maxDepth}
                  maxPaths={maxPaths}
                  excludedKinds={excludedKinds}
                  onMaxDepthChange={setMaxDepth}
                  onMaxPathsChange={setMaxPaths}
                  onExcludedKindsChange={setExcludedKinds}
                />

                {/* Results */}
                {data && data.paths.length > 0 && (
                  <div className="border-gray-200 border-t p-4">
                    <div className="mb-3 flex items-center justify-between">
                      <h3 className="font-medium text-gray-700 text-sm">
                        {data.total_paths_found} path{data.total_paths_found !== 1 ? "s" : ""} found
                      </h3>
                      <button
                        type="button"
                        onClick={() => handleCopyPath(copyAllPathsAsText(data))}
                        className="rounded px-2 py-0.5 text-blue-600 text-xs hover:bg-blue-50"
                        title="Copy all paths to clipboard"
                      >
                        {copyFeedback || "Copy all"}
                      </button>
                    </div>

                    <div className="space-y-1">
                      {data.paths.map((path, index) => (
                        <div
                          key={index}
                          className={`group flex items-start gap-1 rounded-md border p-2 transition-colors ${
                            selectedPathIndex === index
                              ? "border-blue-300 bg-blue-50"
                              : "border-transparent hover:border-gray-200 hover:bg-gray-50"
                          }`}
                        >
                          <button
                            onClick={() => handleSelectPath(index)}
                            className="min-w-0 flex-1 text-left"
                          >
                            <div className="flex items-center gap-2">
                              <span
                                className={`font-medium text-xs ${
                                  selectedPathIndex === index ? "text-blue-700" : "text-gray-600"
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
                            onClick={() => handleCopyPath(formatPathAsText(data, index))}
                            className="mt-0.5 flex-shrink-0 rounded p-0.5 text-gray-300 opacity-0 transition-opacity hover:text-gray-500 group-hover:opacity-100"
                            title="Copy this path"
                          >
                            <svg
                              className="size-3.5"
                              fill="none"
                              viewBox="0 0 24 24"
                              stroke="currentColor"
                              strokeWidth={2}
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                              />
                            </svg>
                          </button>
                        </div>
                      ))}
                    </div>

                    {/* Full text preview of selected path */}
                    {data.paths[selectedPathIndex] && (
                      <div className="mt-3 rounded-md border border-gray-100 bg-gray-50 p-2 text-[11px] text-gray-600 leading-relaxed">
                        {formatPathAsText(data, selectedPathIndex)}
                      </div>
                    )}
                  </div>
                )}

                {data && data.paths.length === 0 && (
                  <div className="border-gray-200 border-t p-4 text-center text-gray-400 text-sm">
                    No paths found
                  </div>
                )}
              </>
            )}

            {mode === "impact" && (
              <>
                <DependencySelector
                  onSearch={handleDepsSearch}
                  isLoading={depsLoading}
                  initialSourceId={initialSourceId}
                />

                {depsData && depsData.reachable_nodes.length > 0 && (
                  <div className="border-gray-200 border-t p-4">
                    <div className="mb-2 rounded-md border border-amber-200 bg-amber-50 p-2">
                      <div className="font-medium text-amber-800 text-xs">
                        {depsData.total_found} node{depsData.total_found !== 1 ? "s" : ""} found
                      </div>
                    </div>
                    <div className="space-y-1">
                      {depsData.reachable_nodes.map((node, index) => (
                        <button
                          key={node.id}
                          onClick={() => handleSelectPath(index)}
                          className={`flex w-full items-center gap-2 rounded-md border p-2 text-left text-xs transition-colors ${
                            selectedPathIndex === index
                              ? "border-amber-300 bg-amber-50"
                              : "border-transparent hover:border-gray-200 hover:bg-gray-50"
                          }`}
                        >
                          <div
                            className="size-2 flex-shrink-0 rounded-full"
                            style={{ backgroundColor: getKindColor(node.kind) }}
                          />
                          <div className="min-w-0 flex-1">
                            <div className="truncate font-medium">{node.display_label}</div>
                            <div className="truncate text-[10px] text-gray-400">
                              {node.kind} &middot; {node.depth} hop{node.depth !== 1 ? "s" : ""}
                            </div>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>

      {/* Right panel: visualization */}
      <div className="relative flex-1">
        {activeError && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="max-w-md rounded-md border border-red-200 bg-red-50 p-4">
              <p className="text-red-700 text-sm">{activeError.message}</p>
            </div>
          </div>
        )}

        {!activeQueryEnabled && !activeError && (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-gray-300">
            <svg
              className="size-16"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={0.8}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.07-9.07a4.5 4.5 0 00-6.364 0l-4.5 4.5a4.5 4.5 0 001.242 7.244"
              />
            </svg>
            <span className="text-sm">
              {mode === "path"
                ? 'Select two nodes and click "Find Paths"'
                : 'Select a source node, target kinds, and click "Find Dependencies"'}
            </span>
          </div>
        )}

        {activeLoading && (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-gray-500">
            <Spinner />
            <span className="text-sm">
              {mode === "path" ? "Finding paths..." : "Finding dependencies..."}
            </span>
          </div>
        )}

        {mode === "path" && data && !isLoading && (
          <PathFlowGraph
            data={data}
            selectedPathIndex={selectedPathIndex}
            onPathSelect={setSelectedPathIndex}
            onExcludeKind={(kind) => {
              setExcludedKinds((prev) => (prev.includes(kind) ? prev : [...prev, kind]));
            }}
          />
        )}

        {mode === "impact" && depsData && !depsLoading && (
          <PathFlowGraph
            data={reachableNodesToPathResponse(depsData)}
            selectedPathIndex={selectedPathIndex}
            onPathSelect={setSelectedPathIndex}
          />
        )}
      </div>
    </div>
  );
}
