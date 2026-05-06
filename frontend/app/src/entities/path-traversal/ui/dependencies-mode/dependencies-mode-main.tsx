import { PathFlowGraph } from "../path-flow-graph";
import { useGetReachableObjects } from "../queries/get-reachable-objects.query";
import { getQueryStateOverlay } from "../query-state-overlay";
import { useDependenciesModeParams } from "./use-dependencies-mode-params";

type DependenciesModeMainProps = {
  parametersOpen: boolean;
  onParametersClick: () => void;
};

export function DependenciesModeMain({
  parametersOpen,
  onParametersClick,
}: DependenciesModeMainProps) {
  const [params, setParams] = useDependenciesModeParams();

  const query = useGetReachableObjects(
    {
      sourceId: params.source,
      targetKinds: params.targetKinds,
      maxDepth: params.depth,
    },
    { enabled: !!params.source && params.targetKinds.length > 0 }
  );

  const data = query.data;

  const overlay = getQueryStateOverlay({
    error: query.error as Error | null,
    isLoading: query.isPending && query.fetchStatus === "fetching",
    isEmpty: !data || data.reachable_objects.length === 0,
    hasRun: !!data,
    loadingMessage: "Finding dependencies...",
    emptyMessage: "No dependencies found",
    idleMessage: 'Select a source object, target kinds, and click "Find Dependencies"',
  });

  // PathFlowGraph requires a `destination`; reachable-objects queries don't have one,
  // so we synthesize it from the first reachable object to satisfy the contract.
  const firstObject = data?.reachable_objects[0];
  const destination = firstObject
    ? {
        id: firstObject.id,
        kind: firstObject.kind,
        display_label: firstObject.display_label,
      }
    : data?.source;

  const graphData =
    data && destination
      ? {
          paths: data.paths,
          source: data.source,
          destination,
          total_paths_found: data.paths.length,
        }
      : null;

  return (
    <PathFlowGraph
      data={graphData}
      selectedPathIndex={params.selectedIndex}
      onPathSelect={(index) => setParams({ selectedIndex: index })}
      parametersOpen={parametersOpen}
      onParametersClick={onParametersClick}
      onReload={data ? () => query.refetch() : undefined}
      isReloading={query.isFetching}
      overlay={overlay}
    />
  );
}
