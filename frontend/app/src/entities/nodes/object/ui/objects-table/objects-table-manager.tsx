import { getObjectsInfiniteQueryOptions } from "@/entities/nodes/object/domain/get-objects.query";
import { ActiveFilterTags } from "@/entities/nodes/object/ui/objects-table/filters/active-filter-tags";
import { FilterResetButton } from "@/entities/nodes/object/ui/objects-table/filters/filter-reset-button";
import { FilterSearchInput } from "@/entities/nodes/object/ui/objects-table/filters/filter-search-input";
import { ObjectsTable } from "@/entities/nodes/object/ui/objects-table/objects-table";
import { useGetObjectPermissions } from "@/entities/permission/domain/get-object-permissions.query";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";
import { queryClient } from "@/shared/api/rest/client";
import ErrorScreen from "@/shared/components/errors/error-screen";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { ObjectCreateFormTrigger } from "@/shared/components/form/object-create-form-trigger";
import LoadingScreen from "@/shared/components/loading-screen";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import useFilters from "@/shared/hooks/useFilters";

export interface ObjectsTableManagerProps {
  schema: IModelSchema;
}

export function ObjectsTableManager({ schema }: ObjectsTableManagerProps) {
  const [filters] = useFilters();
  const { isPending, error, data: permissions } = useGetObjectPermissions(schema.kind as string);

  if (isPending) return <LoadingScreen />;

  if (error) return <ErrorScreen message={error.message} />;

  if (!permissions.view.isAllowed) {
    return <UnauthorizedScreen message={permissions.view.message} />;
  }

  return (
    <div>
      <div className="flex items-center h-14 px-3">
        <FilterSearchInput schema={schema} />

        <ScrollArea scrollX>
          <ActiveFilterTags schema={schema} className="mx-2" />
        </ScrollArea>

        {filters.length > 0 && <FilterResetButton />}

        <ObjectCreateFormTrigger
          schema={schema}
          onSuccess={() => {
            queryClient.invalidateQueries(getObjectsInfiniteQueryOptions({ schema, filters }));
          }}
          permission={permissions}
          className="ml-auto"
        />
      </div>

      <ObjectsTable schema={schema} />
    </div>
  );
}
