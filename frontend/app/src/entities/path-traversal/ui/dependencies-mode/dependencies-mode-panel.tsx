import { useState } from "react";
import { useForm } from "react-hook-form";

import { useGetReachableObjects } from "../queries/get-reachable-objects.query";
import { DependenciesModeForm } from "./dependencies-mode-form";
import { DependenciesModeResults } from "./dependencies-mode-results";
import {
  type DependenciesModeFormValues,
  formValuesToParams,
  paramsToFormValues,
  useDependenciesModeParams,
} from "./use-dependencies-mode-params";

export function DependenciesModePanel() {
  const [params, setParams] = useDependenciesModeParams();
  const formValues = paramsToFormValues(params);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const form = useForm<DependenciesModeFormValues>({
    defaultValues: formValues,
    values: formValues,
  });

  const query = useGetReachableObjects(
    {
      sourceId: params.source,
      targetKinds: params.targetKinds,
      maxDepth: params.depth,
    },
    { enabled: !!params.source && params.targetKinds.length > 0 }
  );

  return (
    <div className="flex h-full flex-col">
      <DependenciesModeForm
        form={form}
        onSubmit={(values) => {
          setParams(formValuesToParams(values));
          setSelectedIndex(0);
        }}
        isPending={query.isFetching}
      />
      <div className="flex-1 overflow-hidden">
        <DependenciesModeResults
          data={query.data}
          isLoading={query.isLoading}
          error={query.error as Error | null}
          selectedIndex={selectedIndex}
          onSelectIndex={setSelectedIndex}
        />
      </div>
    </div>
  );
}
