import { useAuth } from "@/entities/authentication/ui/useAuth";
import { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { cellHeaderStyle, cellsStyle } from "@/entities/nodes/object/ui/objects-table/cells/style";
import { TableColumnHeaderIcon } from "@/entities/nodes/object/ui/objects-table/cells/table-column-header-icon";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";
import { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";
import { getFiltersFromFormData } from "@/shared/components/filters/utils/getFiltersFromFormData";
import { getObjectFromFilters } from "@/shared/components/filters/utils/getObjectFromFilters";
import DynamicForm from "@/shared/components/form/dynamic-form";
import { FormFieldValue } from "@/shared/components/form/type";
import { getFormFieldFromAttribute } from "@/shared/components/form/utils/getFormFieldFromAttribute";
import { getFormFieldFromRelationship } from "@/shared/components/form/utils/getFormFieldFromRelationship";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import useFilters from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";

export interface TableColumnHeaderProps {
  schema: IModelSchema;
  columnSchema: AttributeSchema | RelationshipSchema;
}

export function TableColumnHeader({ schema, columnSchema }: TableColumnHeaderProps) {
  const auth = useAuth();
  const [filters, setFilters] = useFilters();
  const [showFilters, setShowFilters] = useState(false);
  const filtersAsObjectData = getObjectFromFilters(schema, filters);
  const currentColumnFilters = filtersAsObjectData[columnSchema.name];

  const handleSubmit = (formData: Record<string, FormFieldValue>) => {
    const newFilters = getFiltersFromFormData(formData);

    setFilters([...filters, ...newFilters]);
    setShowFilters(false);
  };

  const field =
    "peer" in columnSchema
      ? getFormFieldFromRelationship({
          auth,
          schema,
          isFilterForm: true,
          relationshipSchema: columnSchema,
          relationshipData: filtersAsObjectData[columnSchema.name] as RelationshipType | undefined,
        })
      : getFormFieldFromAttribute({
          auth,
          schema,
          isFilterForm: true,
          attributeSchema: columnSchema,
          currentObject: filtersAsObjectData as Record<string, AttributeType>,
        });

  return (
    <Popover open={showFilters} onOpenChange={setShowFilters}>
      <PopoverTrigger className={classNames(cellsStyle, cellHeaderStyle)}>
        <TableColumnHeaderIcon fieldSchema={columnSchema} />

        <span className="truncate mr-2">{columnSchema.label ?? columnSchema.name}</span>
        <Icon
          icon="mdi:filter-variant"
          className={classNames(
            "text-lg ml-auto",
            currentColumnFilters ? "text-indigo-700" : "invisible"
          )}
        />
      </PopoverTrigger>

      <PopoverContent className="min-w-[19rem]">
        <DynamicForm
          fields={[field]}
          onSubmit={handleSubmit}
          onCancel={() => setShowFilters(false)}
          submitLabel="Filter"
        />
      </PopoverContent>
    </Popover>
  );
}
