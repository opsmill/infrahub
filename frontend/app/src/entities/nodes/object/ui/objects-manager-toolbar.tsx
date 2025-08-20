import { reloadIpamTreeAtom } from "@/entities/ipam/ipam-tree/ipam-tree.state";
import { ActiveObjectFilterTags } from "@/entities/nodes/object/ui/filters/active-object-filter-tags";
import { FilterSearchInput } from "@/entities/nodes/object/ui/filters/filter-search-input";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectTableSchemaSelector } from "@/entities/nodes/object/ui/object-table/object-table-schema-selector";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";
import { queryClient } from "@/shared/api/rest/client";
import { ObjectCreateFormTrigger } from "@/shared/components/form/object-create-form-trigger";
import {} from "@/shared/components/ui/combobox";
import { useSetAtom } from "jotai";
import { useLocation, useParams } from "react-router";

export function ObjectsManagerToolbar() {
  const { objectId } = useParams();

  const location = useLocation();
  const reloadIpamTree = useSetAtom(reloadIpamTreeAtom);
  const { selectedSchema, baseSchema, permission } = useObjectTableContext();

  return (
    <div className="flex items-center gap-2 h-14 px-3 shrink-0">
      {isGenericSchema(baseSchema) && (baseSchema.used_by ?? []).length > 1 && (
        <ObjectTableSchemaSelector />
      )}

      <FilterSearchInput schema={selectedSchema} />

      <ActiveObjectFilterTags schema={selectedSchema} />

      <ObjectCreateFormTrigger
        schema={selectedSchema}
        onSuccess={() => {
          queryClient.invalidateQueries({
            predicate: (query) => query.queryKey.includes("objects"),
          });

          if (location.pathname.startsWith("/ipam")) {
            reloadIpamTree(objectId);
          }
        }}
        permission={permission}
        className="ml-auto"
      />
    </div>
  );
}
