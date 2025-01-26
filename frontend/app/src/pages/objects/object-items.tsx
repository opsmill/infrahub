import { ActiveFilterTags } from "@/entities/nodes/object/ui/objects-table/filters/active-filter-tags";
import { FilterResetButton } from "@/entities/nodes/object/ui/objects-table/filters/filter-reset-button";
import { FilterSearchInput } from "@/entities/nodes/object/ui/objects-table/filters/filter-search-input";
import { ObjectsTable } from "@/entities/nodes/object/ui/objects-table/objects-table";
import { useSchema } from "@/entities/schema/hooks/useSchema";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { ScrollArea } from "@/shared/components/ui/scroll-area";
import useFilters from "@/shared/hooks/useFilters";
import { useParams } from "react-router-dom";

export function ObjectItemsPage() {
  const { objectKind } = useParams();
  const [filters] = useFilters();

  const { schema } = useSchema(objectKind);
  if (!schema) return <ErrorScreen message={`Object ${objectKind} not found.`} />;

  return (
    <div>
      <div className="flex items-center gap-2 h-14 px-3">
        <FilterSearchInput schema={schema} />

        <ScrollArea scrollX>
          <ActiveFilterTags schema={schema} />
        </ScrollArea>

        {filters.length > 0 && <FilterResetButton />}
      </div>

      <ObjectsTable schema={schema} />
    </div>
  );
}

export const Component = ObjectItemsPage;
