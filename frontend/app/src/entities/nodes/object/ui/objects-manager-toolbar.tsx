import { queryClient } from "@/shared/api/rest/client";
import { ObjectCreateFormTrigger } from "@/shared/components/form/object-create-form-trigger";

import { ActiveObjectFilterTags } from "@/entities/nodes/object/ui/filters/active-object-filter-tags";
import { FilterSearchInput } from "@/entities/nodes/object/ui/filters/filter-search-input";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectTableSchemaSelector } from "@/entities/nodes/object/ui/object-table/object-table-schema-selector";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";

export function ObjectsManagerToolbar() {
  const { selectedSchema, baseSchema, permission } = useObjectTableContext();

  return (
    <div className="flex h-14 shrink-0 items-center gap-2 px-3">
      {isGenericSchema(baseSchema) && (baseSchema.used_by ?? []).length > 1 && (
        <ObjectTableSchemaSelector />
      )}

      <FilterSearchInput schema={selectedSchema} />

      <ActiveObjectFilterTags schema={selectedSchema} />

      <ObjectCreateFormTrigger
        schema={selectedSchema}
        onSuccess={() => {
          queryClient.invalidateQueries({
            queryKey: objectQueryKeys.all,
          });
        }}
        permission={permission}
        className="ml-auto"
      />
    </div>
  );
}
