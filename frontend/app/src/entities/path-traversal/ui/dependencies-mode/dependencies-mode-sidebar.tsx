import { useForm } from "react-hook-form";

import { copyEntriesAsText, formatPathHopsAsText } from "../format-paths";
import { PathResultsList } from "../path-results-list";
import { useGetReachableNodes } from "../queries/get-reachable-nodes.query";
import { DependenciesModeForm } from "./dependencies-mode-form";
import {
  type DependenciesModeFormValues,
  formValuesToParams,
  paramsToFormValues,
  useDependenciesModeParams,
} from "./use-dependencies-mode-params";

export function DependenciesModeSidebar() {
  const [params, setParams] = useDependenciesModeParams();
  const formValues = paramsToFormValues(params);

  const form = useForm<DependenciesModeFormValues>({
    defaultValues: formValues,
    values: formValues,
  });

  const query = useGetReachableNodes(
    {
      sourceId: params.source,
      targetKinds: params.targetKinds,
      maxDepth: params.depth,
    },
    { enabled: !!params.source && params.targetKinds.length > 0 }
  );

  const data = query.data;
  const paths = data?.dependencies.map((dep) => dep.path) ?? [];

  return (
    <div className="flex h-full flex-col">
      <DependenciesModeForm
        form={form}
        onSubmit={(values) => setParams(formValuesToParams(values))}
        isPending={query.isPending && query.fetchStatus === "fetching"}
      />

      {data && (
        <PathResultsList
          paths={paths}
          countLabel={`${data.count} dependenc${data.count === 1 ? "y" : "ies"} found`}
          selectedIndex={params.selectedIndex}
          onSelect={(index) => setParams({ selectedIndex: index })}
          variant="amber"
          getItemTitle={(_, index) => data.dependencies[index]?.node.display_label ?? ""}
          getItemSubtitle={(_, index) => data.dependencies[index]?.node.kind}
          emptyMessage="No dependencies found"
          copyAllText={() =>
            copyEntriesAsText(paths, (_, i) => data.dependencies[i]?.node.display_label ?? "")
          }
          copyItemText={(index) => formatPathHopsAsText(paths[index]!)}
          ariaLabel="Dependency results"
        />
      )}
    </div>
  );
}
