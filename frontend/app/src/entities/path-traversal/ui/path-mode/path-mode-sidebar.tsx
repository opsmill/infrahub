import { useForm } from "react-hook-form";

import { copyAllPathsAsText, formatPathAsText } from "../format-paths";
import { PathResultsList } from "../path-results-list";
import { useGetPathTraversal } from "../queries/get-path-traversal.query";
import { PathModeForm } from "./path-mode-form";
import {
  formValuesToParams,
  type PathModeFormValues,
  paramsToFormValues,
  usePathModeParams,
} from "./use-path-mode-params";

export function PathModeSidebar() {
  const [params, setParams] = usePathModeParams();
  const formValues = paramsToFormValues(params);

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

  const data = query.data;

  return (
    <div className="flex h-full flex-col">
      <PathModeForm
        form={form}
        onSubmit={(values) => setParams(formValuesToParams(values))}
        isPending={query.isPending && query.fetchStatus === "fetching"}
      />

      {data && (
        <PathResultsList
          paths={data.paths}
          countLabel={`${data.count} path${data.count !== 1 ? "s" : ""} found`}
          selectedIndex={params.selectedPath}
          onSelect={(index) => setParams({ selectedPath: index })}
          variant="blue"
          getItemTitle={(_, index) => `Path ${index + 1}`}
          emptyMessage="No paths found"
          copyAllText={() => copyAllPathsAsText(data)}
          copyItemText={(index) => formatPathAsText(data, index)}
          ariaLabel="Path results"
        />
      )}
    </div>
  );
}
