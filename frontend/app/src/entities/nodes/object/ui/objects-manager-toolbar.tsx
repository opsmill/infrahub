import { queryClient } from "@/shared/api/rest/client";
import { Col, Row } from "@/shared/components/container";
import { ObjectCreateFormTrigger } from "@/shared/components/form/object-create-form-trigger";

import { ColumnsPicker } from "@/entities/nodes/columns/ui/columns-picker";
import { ActiveObjectFilterTags } from "@/entities/nodes/object/ui/filters/active-object-filter-tags";
import { FilterPicker } from "@/entities/nodes/object/ui/filters/filter-picker";
import { FilterSearchInput } from "@/entities/nodes/object/ui/filters/filter-search-input";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectTableSchemaSelector } from "@/entities/nodes/object/ui/object-table/object-table-schema-selector";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import { SortPicker } from "@/entities/nodes/sort/ui/sort-picker";
import { isGenericSchema } from "@/entities/schema/domain/rules/is-generic-schema";

export function ObjectsManagerToolbar() {
  const {
    selectedSchema,
    baseSchema,
    filters,
    permission,
    columnSurface,
    supportsColumnVisibility,
  } = useObjectTableContext();

  return (
    <Col className="shrink-0 gap-0">
      <Row className="p-2">
        {isGenericSchema(baseSchema) && (baseSchema.used_by ?? []).length > 1 && (
          <ObjectTableSchemaSelector />
        )}

        <FilterSearchInput schema={selectedSchema} />

        <SortPicker schema={selectedSchema} />

        {/* Only tables that honour the column-visibility params get the picker: elsewhere it
            would write the URL and change nothing. */}
        {supportsColumnVisibility && (
          <ColumnsPicker schema={selectedSchema} surface={columnSurface} />
        )}

        <FilterPicker schema={selectedSchema} filters={filters} />

        <ObjectCreateFormTrigger
          schema={selectedSchema}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
          }}
          permission={permission}
          className="ml-auto"
        />
      </Row>

      <ActiveObjectFilterTags schema={selectedSchema} />
    </Col>
  );
}
