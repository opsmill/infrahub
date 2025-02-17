import { ActiveFilterTags } from "@/entities/nodes/object/ui/filters/active-filter-tags";
import { FilterResetButton } from "@/entities/nodes/object/ui/filters/filter-reset-button";
import { FilterSearchInput } from "@/entities/nodes/object/ui/filters/filter-search-input";
import { ObjectTable } from "@/entities/nodes/object/ui/object-table/object-table";
import { useGetObjectPermissions } from "@/entities/permission/domain/get-object-permissions.query";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";
import { queryClient } from "@/shared/api/rest/client";
import ErrorScreen from "@/shared/components/errors/error-screen";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { ObjectCreateFormTrigger } from "@/shared/components/form/object-create-form-trigger";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import useFilters from "@/shared/hooks/useFilters";

export interface ObjectsTableManagerProps {
  schema: IModelSchema;
}

export function ObjectsManager({ schema }: ObjectsTableManagerProps) {
  const [filters] = useFilters();
  const { isPending, error, data: permission } = useGetObjectPermissions(schema.kind as string);

  if (isPending) return <LoadingIndicator className="h-[calc(100vh-10.5rem)]" />;

  if (error) return <ErrorScreen message={error.message} />;

  if (!permission.view.isAllowed) {
    return <UnauthorizedScreen message={permission.view.message} />;
  }

  return (
    <>
      <div className="flex items-center h-14 px-3 shrink-0">
        <FilterSearchInput schema={schema} />

        {filters.length > 0 && (
          <>
            <ScrollArea scrollX>
              <ActiveFilterTags schema={schema} className="mx-2" />
            </ScrollArea>
            <FilterResetButton />
          </>
        )}

        <ObjectCreateFormTrigger
          schema={schema}
          onSuccess={() => {
            queryClient.invalidateQueries({
              predicate: (query) => query.queryKey.includes("objects"),
            });
          }}
          permission={permission}
          className="ml-auto"
        />
      </div>

      <ObjectTable schema={schema} permission={permission} />
    </>
  );
}
