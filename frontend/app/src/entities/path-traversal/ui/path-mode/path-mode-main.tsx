import { Spinner } from "@infrahub/ui";

import { PathFlowGraph } from "../path-flow-graph";
import { useGetPathTraversal } from "../queries/get-path-traversal.query";
import { usePathModeParams } from "./use-path-mode-params";

export function PathModeMain() {
  const [params, setParams] = usePathModeParams();

  const query = useGetPathTraversal(
    {
      sourceId: params.source,
      destinationId: params.destination,
      maxDepth: params.depth,
      maxPaths: params.maxPaths,
      kindFilter: params.kindFilter,
      excludedKinds: params.excludedKinds,
    },
    { enabled: !!params.source && !!params.destination }
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
        <span className="text-sm">Finding paths...</span>
      </div>
    );
  }

  if (!query.data || query.data.paths.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-gray-300 text-sm">
        {query.data ? "No paths found" : 'Select two objects and click "Find Paths"'}
      </div>
    );
  }

  return (
    <PathFlowGraph
      data={query.data}
      selectedPathIndex={params.selectedPath}
      onPathSelect={(index) => setParams({ selectedPath: index })}
      onExcludeKind={(kind) =>
        setParams((prev) => ({
          excludedKinds: prev.excludedKinds.includes(kind)
            ? prev.excludedKinds
            : [...prev.excludedKinds, kind],
        }))
      }
    />
  );
}
