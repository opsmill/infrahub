import { ColumnDef } from "@tanstack/react-table";
import * as R from "remeda";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import {
  AttributeType,
  ObjectAttributeValue,
  RelationshipType,
} from "@/entities/nodes/getObjectItemDisplayValue";
import { getAttributesVisibleInListView } from "@/entities/nodes/object/utils/get-attributes-visible-in-list";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";
import { getFiltersFromFormData } from "@/shared/components/filters/utils/getFiltersFromFormData";
import { getObjectFromFilters } from "@/shared/components/filters/utils/getObjectFromFilters";
import DynamicForm from "@/shared/components/form/dynamic-form";
import { FormFieldValue } from "@/shared/components/form/type";
import { getFormFieldFromAttribute } from "@/shared/components/form/utils/getFormFieldFromAttribute";
import { getFormFieldFromRelationship } from "@/shared/components/form/utils/getFormFieldFromRelationship";
import { Badge } from "@/shared/components/ui/badge";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import useFilters from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";

export const getObjectTableColumns = (
  schema: IModelSchema
): ColumnDef<Record<string, AttributeType | RelationshipType>>[] => {
  const attributes = getAttributesVisibleInListView(schema.attributes ?? []);
  const relationships = getRelationshipsVisibleInListView(schema.relationships ?? []);
  const sortedColumns = R.pipe(
    [...attributes, ...relationships],
    R.sortBy((column) => column.order_weight ?? 0)
  );

  return [
    {
      header: "ID",
      accessorKey: "id",
      cell: ({ row }) => {
        const value = (row.getValue("id") ?? "-") as string;
        return <Badge variant="blue">{value}</Badge>;
      },
    },
    ...sortedColumns.map((column) => {
      return {
        header: () => {
          const auth = useAuth();
          const [filters, setFilters] = useFilters();
          const [showFilters, setShowFilters] = useState(false);
          const filtersAsObjectData = getObjectFromFilters(schema, filters);
          const currentColumnFilters = filtersAsObjectData[column.name];

          const handleSubmit = (formData: Record<string, FormFieldValue>) => {
            const newFilters = getFiltersFromFormData(formData);

            setFilters([...filters, ...newFilters]);
            setShowFilters(false);
          };

          const field =
            "peer" in column
              ? getFormFieldFromRelationship({
                  auth,
                  schema,
                  isFilterForm: true,
                  relationshipSchema: column,
                  relationshipData: filtersAsObjectData[column.name] as
                    | RelationshipType
                    | undefined,
                })
              : getFormFieldFromAttribute({
                  auth,
                  schema,
                  isFilterForm: true,
                  attributeSchema: column,
                  currentObject: filtersAsObjectData as Record<string, AttributeType>,
                });

          return (
            <Popover open={showFilters} onOpenChange={setShowFilters}>
              <PopoverTrigger className="flex items-center gap-1.5 p-2">
                {column.label ?? column.name}
                <Icon
                  icon="mdi:filter-variant"
                  className={classNames(
                    "text-lg",
                    currentColumnFilters ? "text-indigo-700" : "text-gray-300"
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
        },
        accessorKey: column.name,
        cell: ({ row }) => {
          const value = row.getValue(column.name);
          return <ObjectAttributeValue attributeSchema={column} attributeValue={value} />;
        },
      };
    }),
  ];
};
