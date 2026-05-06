import { useForm } from "react-hook-form";

import { useGetReachableObjects } from "../queries/get-reachable-objects.query";
import { getKindColor } from "../utils";
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

  const query = useGetReachableObjects(
    {
      sourceId: params.source,
      targetKinds: params.targetKinds,
      maxDepth: params.depth,
    },
    { enabled: !!params.source && params.targetKinds.length > 0 }
  );

  const data = query.data;

  return (
    <div className="flex h-full flex-col">
      <DependenciesModeForm
        form={form}
        onSubmit={(values) => setParams(formValuesToParams(values))}
        isPending={query.isPending && query.fetchStatus === "fetching"}
      />

      {data && (
        <div className="border-gray-200 border-t p-4">
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
                onClick={() => setParams({ selectedIndex: index })}
                className={`flex w-full items-center gap-2 rounded-md border p-2 text-left text-xs transition-colors ${
                  params.selectedIndex === index
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
      )}
    </div>
  );
}
