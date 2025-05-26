import { ActiveFilterTags } from "@/entities/nodes/object/ui/filters/active-filter-tags";
import { FilterResetButton } from "@/entities/nodes/object/ui/filters/filter-reset-button";
import { FilterSearchInput } from "@/entities/nodes/object/ui/filters/filter-search-input";
import { Permission } from "@/entities/permission/types";
import { ModelSchema } from "@/entities/schema/types";
import { queryClient } from "@/shared/api/rest/client";
import { ObjectCreateFormTrigger } from "@/shared/components/form/object-create-form-trigger";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import useFilters from "@/shared/hooks/useFilters";

export interface ObjectsManagerToolbarProps {
  schema: ModelSchema;
  permission: Permission;
}

export function ObjectsManagerToolbar({ schema, permission }: ObjectsManagerToolbarProps) {
  const [filters] = useFilters();

  return (
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
  );
}
