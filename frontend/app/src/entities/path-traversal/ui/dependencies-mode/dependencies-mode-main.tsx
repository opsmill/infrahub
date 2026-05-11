import { PathFlowGraph } from "../path-flow-graph";
import { useGetReachableNodes } from "../queries/get-reachable-nodes.query";
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

  const query = useGetReachableNodes(
    {
      sourceId: params.source,
      targetKinds: params.targetKinds,
      maxDepth: params.depth,
    },
    { enabled: !!params.source && params.targetKinds.length > 0 }
  );

  const data = query.data;

  const paths = data ? data.dependencies.map((dep) => dep.path) : [];
  const destinationIds = new Set(data ? data.dependencies.map((dep) => dep.node.id) : []);

  const overlay = getQueryStateOverlay({
    error: query.error as Error | null,
    isLoading: query.isPending && query.fetchStatus === "fetching",
    isEmpty: !data || data.dependencies.length === 0,
    hasRun: !!data,
    loadingMessage: "Finding dependencies...",
    emptyMessage: "No dependencies found",
    idleMessage: 'Select a source object, target kinds, and click "Find Dependencies"',
  });

  return (
    <PathFlowGraph
      paths={paths}
      sourceId={data?.source.id ?? ""}
      destinationIds={destinationIds}
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
