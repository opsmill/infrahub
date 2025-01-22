import { ColumnDef } from "@tanstack/react-table";
import * as R from "remeda";

import {
  AttributeType,
  ObjectAttributeValue,
  RelationshipType,
} from "@/entities/nodes/getObjectItemDisplayValue";
import { getAttributesVisibleInListView } from "@/entities/nodes/object/utils/get-attributes-visible-in-list";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";

export const getObjectTableColumns = (
  schema: IModelSchema
): ColumnDef<Record<string, AttributeType | RelationshipType>>[] => {
  const attributes = getAttributesVisibleInListView(schema.attributes ?? []);
  const relationships = getRelationshipsVisibleInListView(schema.relationships ?? []);
  const sortedColumns = R.pipe(
    [...attributes, ...relationships],
    R.sortBy((column) => column.order_weight ?? 0)
  );

  return sortedColumns.map((column) => {
    return {
      header: column.label ?? column.name,
      accessorKey: column.name,
      cell: ({ row }) => {
        const value = row.getValue(column.name);
        return <ObjectAttributeValue attributeSchema={column} attributeValue={value} />;
      },
    };
  });
};
