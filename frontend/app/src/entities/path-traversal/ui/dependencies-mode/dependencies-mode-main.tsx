import { Spinner } from "@infrahub/ui";

import { PathFlowGraph } from "../path-flow-graph";
import { useGetReachableObjects } from "../queries/get-reachable-objects.query";
import { useDependenciesModeParams } from "./use-dependencies-mode-params";

export function DependenciesModeMain() {
  const [params, setParams] = useDependenciesModeParams();

  const query = useGetReachableObjects(
    {
      sourceId: params.source,
      targetKinds: params.targetKinds,
      maxDepth: params.depth,
    },
    { enabled: !!params.source && params.targetKinds.length > 0 }
  );

  if (query.error) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="max-w-md rounded-md border border-red-200 bg-red-50 p-4">
          <p className="text-red-700 text-sm">{(query.error as Error).message}</p>
        </div>
      </div>
    );
  }

  if (query.isPending && query.fetchStatus === "fetching") {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-gray-500">
        <Spinner />
        <span className="text-sm">Finding dependencies...</span>
      </div>
    );
  }

  const data = query.data;
  if (!data || data.reachable_objects.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-gray-300 text-sm">
        {data
          ? "No dependencies found"
          : 'Select a source object, target kinds, and click "Find Dependencies"'}
      </div>
    );
  }

  // PathFlowGraph requires a `destination`. Use the first reachable object as
  // a synthetic destination here.
  const firstObject = data.reachable_objects[0];
  const destination = firstObject
    ? {
        id: firstObject.id,
        kind: firstObject.kind,
        display_label: firstObject.display_label,
      }
    : data.source;

  return (
    <PathFlowGraph
      data={{
        paths: data.paths,
        source: data.source,
        destination,
        total_paths_found: data.paths.length,
      }}
      selectedPathIndex={params.selectedIndex}
      onPathSelect={(index) => setParams({ selectedIndex: index })}
    />
  );
}
