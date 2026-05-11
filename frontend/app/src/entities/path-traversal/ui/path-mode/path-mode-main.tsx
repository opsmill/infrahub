import { PathFlowGraph } from "../path-flow-graph";
import { useGetPathTraversal } from "../queries/get-path-traversal.query";
import { getQueryStateOverlay } from "../query-state-overlay";
import { usePathModeParams } from "./use-path-mode-params";

type PathModeMainProps = {
  parametersOpen: boolean;
  onParametersClick: () => void;
};

export function PathModeMain({ parametersOpen, onParametersClick }: PathModeMainProps) {
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

  const data = query.data;
  const destinationIds = new Set(data ? [data.destination.id] : []);

  const overlay = getQueryStateOverlay({
    error: query.error as Error | null,
    isLoading: query.isPending && query.fetchStatus === "fetching",
    isEmpty: !data || data.paths.length === 0,
    hasRun: !!data,
    loadingMessage: "Finding paths...",
    emptyMessage: "No paths found",
    idleMessage: 'Select two objects and click "Find Paths"',
  });

  return (
    <PathFlowGraph
      paths={data?.paths ?? []}
      sourceId={data?.source.id ?? ""}
      destinationIds={destinationIds}
      selectedPathIndex={params.selectedPath}
      onPathSelect={(index) => setParams({ selectedPath: index })}
      onExcludeKind={(kind) =>
        setParams((prev) => ({
          excludedKinds: prev.excludedKinds.includes(kind)
            ? prev.excludedKinds
            : [...prev.excludedKinds, kind],
        }))
      }
      parametersOpen={parametersOpen}
      onParametersClick={onParametersClick}
      onReload={data ? () => query.refetch() : undefined}
      isReloading={query.isFetching}
      overlay={overlay}
    />
  );
}
