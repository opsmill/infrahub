import { useForm } from "react-hook-form";

import { useGetPathTraversal } from "../queries/get-path-traversal.query";
import { PathModeForm } from "./path-mode-form";
import { PathModeResults } from "./path-mode-results";
import {
  formValuesToParams,
  type PathModeFormValues,
  paramsToFormValues,
  usePathModeParams,
} from "./use-path-mode-params";

export function PathModePanel() {
  const [params, setParams] = usePathModeParams();
  const formValues = paramsToFormValues(params);

  // RHF auto-resets the form when `values` deep-changes; no useEffect needed.
  const form = useForm<PathModeFormValues>({
    defaultValues: formValues,
    values: formValues,
  });

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

  return (
    <div className="flex h-full flex-col">
      <PathModeForm
        form={form}
        onSubmit={(values) => setParams(formValuesToParams(values))}
        isPending={query.isFetching}
      />
      <div className="flex-1 overflow-hidden">
        <PathModeResults
          data={query.data}
          isLoading={query.isLoading}
          error={query.error as Error | null}
          selectedPath={params.selectedPath}
          onSelectPath={(index) => setParams({ selectedPath: index })}
          onExcludeKind={(kind) =>
            setParams((prev) => ({
              excludedKinds: prev.excludedKinds.includes(kind)
                ? prev.excludedKinds
                : [...prev.excludedKinds, kind],
            }))
          }
        />
      </div>
    </div>
  );
}
