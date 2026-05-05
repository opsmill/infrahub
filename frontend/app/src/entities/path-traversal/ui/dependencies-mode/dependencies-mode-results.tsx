import { Spinner } from "@infrahub/ui";

import type { ReachableObjectsResponse } from "../../domain/path-traversal.types";
import { PathFlowGraph } from "../path-flow-graph";
import { getKindColor } from "../utils";

type DependenciesModeResultsProps = {
  data: ReachableObjectsResponse | undefined;
  isLoading: boolean;
  error: Error | null;
  selectedIndex: number;
  onSelectIndex: (index: number) => void;
};

export function DependenciesModeResults({
  data,
  isLoading,
  error,
  selectedIndex,
  onSelectIndex,
}: DependenciesModeResultsProps) {
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
        <span className="text-sm">Finding dependencies...</span>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex h-full items-center justify-center text-gray-300 text-sm">
        Select a source object, target kinds, and click "Find Dependencies"
      </div>
    );
  }

  // PathFlowGraph requires a `destination`. Use the first reachable object as
  // a synthetic destination here. Review item #7 will replace this with an
  // optional destination prop in a separate PR.
  const firstObject = data.reachable_objects[0];
  const destination = firstObject
    ? {
        id: firstObject.id,
        kind: firstObject.kind,
        display_label: firstObject.display_label,
      }
    : data.source;

  return (
    <div className="flex h-full flex-col">
      <div className="border-gray-200 border-b p-4">
        <div className="mb-2 rounded-md border border-amber-200 bg-amber-50 p-2">
          <div className="font-medium text-amber-800 text-xs">
            {data.total_found} object{data.total_found !== 1 ? "s" : ""} found
          </div>
        </div>
        <div className="space-y-1">
          {data.reachable_objects.map((object, index) => (
            <button
              key={object.id}
              type="button"
              onClick={() => onSelectIndex(index)}
              className={`flex w-full items-center gap-2 rounded-md border p-2 text-left text-xs transition-colors ${
                selectedIndex === index
                  ? "border-amber-300 bg-amber-50"
                  : "border-transparent hover:border-gray-200 hover:bg-gray-50"
              }`}
            >
              <div
                className="size-2 flex-shrink-0 rounded-full"
                style={{ backgroundColor: getKindColor(object.kind) }}
              />
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium">{object.display_label}</div>
                <div className="truncate text-[10px] text-gray-400">
                  {object.kind} · {object.depth} hop{object.depth !== 1 ? "s" : ""}
                </div>
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="relative flex-1">
        <PathFlowGraph
          data={{
            paths: data.paths,
            source: data.source,
            destination,
            total_paths_found: data.paths.length,
          }}
          selectedPathIndex={selectedIndex}
          onPathSelect={onSelectIndex}
        />
      </div>
    </div>
  );
}
