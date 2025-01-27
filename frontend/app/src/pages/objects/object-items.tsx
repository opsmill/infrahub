import { getObjectsInfiniteQueryOptions } from "@/entities/nodes/object/domain/get-objects.query";
import { ActiveFilterTags } from "@/entities/nodes/object/ui/objects-table/filters/active-filter-tags";
import { FilterResetButton } from "@/entities/nodes/object/ui/objects-table/filters/filter-reset-button";
import { FilterSearchInput } from "@/entities/nodes/object/ui/objects-table/filters/filter-search-input";
import { ObjectsTable } from "@/entities/nodes/object/ui/objects-table/objects-table";
import { useGetObjectPermissions } from "@/entities/permission/domain/get-object-permissions.query";
import { useSchema } from "@/entities/schema/hooks/useSchema";
import { queryClient } from "@/shared/api/rest/client";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { ObjectCreateFormTrigger } from "@/shared/components/form/object-create-form-trigger";
import LoadingScreen from "@/shared/components/loading-screen";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import useFilters from "@/shared/hooks/useFilters";
import { useParams } from "react-router-dom";

export function ObjectItemsPage() {
  const { objectKind } = useParams();
  const [filters] = useFilters();

  const { schema } = useSchema(objectKind);
  const { isPending, error, data: permissions } = useGetObjectPermissions(objectKind as string);

  if (!schema) return <ErrorScreen message={`Object ${objectKind} not found.`} />;

  if (isPending) return <LoadingScreen />;

  if (error) return <ErrorScreen message={error.message} />;

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

      <ObjectsTable schema={schema} permissions={permissions} />
    </div>
  );
}

export const Component = ObjectItemsPage;
