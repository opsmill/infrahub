import { queryClient } from "@/shared/api/rest/client";
import { Col, Row } from "@/shared/components/container";
import { ObjectCreateFormTrigger } from "@/shared/components/form/object-create-form-trigger";

import { ActiveObjectFilterTags } from "@/entities/nodes/object/ui/filters/active-object-filter-tags";
import { FilterMenu } from "@/entities/nodes/object/ui/filters/filter-menu";
import { FilterSearchInput } from "@/entities/nodes/object/ui/filters/filter-search-input";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectTableSchemaSelector } from "@/entities/nodes/object/ui/object-table/object-table-schema-selector";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";

export function ObjectsManagerToolbar() {
  const { selectedSchema, baseSchema, filters, permission } = useObjectTableContext();

  return (
    <Col className="shrink-0 gap-3 p-3">
      <Row>
        {isGenericSchema(baseSchema) && (baseSchema.used_by ?? []).length > 1 && (
          <ObjectTableSchemaSelector />
        )}

        <FilterSearchInput schema={selectedSchema} />

        <FilterMenu schema={selectedSchema} filters={filters} />

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
      </Row>

      <ActiveObjectFilterTags schema={selectedSchema} />
    </Col>
  );
}
