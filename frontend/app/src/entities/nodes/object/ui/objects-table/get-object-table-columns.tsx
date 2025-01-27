import { ColumnDef } from "@tanstack/react-table";
import * as R from "remeda";

import { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { cellHeaderStyle, cellsStyle } from "@/entities/nodes/object/ui/objects-table/cells/style";
import { TableAttributeCell } from "@/entities/nodes/object/ui/objects-table/cells/table-attribute-cell";
import { TableCell } from "@/entities/nodes/object/ui/objects-table/cells/table-cell";
import { TableColumnHeader } from "@/entities/nodes/object/ui/objects-table/cells/table-column-header";
import { TableRelationshipCell } from "@/entities/nodes/object/ui/objects-table/cells/table-relationship-cell";
import { TableRowIdentifier } from "@/entities/nodes/object/ui/objects-table/cells/table-row-identifier";
import { getAttributesVisibleInListView } from "@/entities/nodes/object/utils/get-attributes-visible-in-list";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";

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
      id: "id",
      accessorFn: (row) => row.hfid ?? row.display_label ?? row.id,
      header: () => (
        <div className={classNames(cellsStyle, cellHeaderStyle, "left-0 z-10")}>
          <Icon icon="mdi:card-account-details-outline" />
          <span className="truncate">{schema.label}</span>
        </div>
      ),
      cell: ({ row }) => {
        const value = (row.getValue("id") ?? "-") as string;
        return (
          <TableRowIdentifier
            objectKind={schema.kind as string}
            objectId={row.original.id as string}
            identifier={value}
          />
        );
      },
    },
    ...sortedColumns.map((columnSchema) => {
      return {
        accessorKey: columnSchema.name,
        header: () => <TableColumnHeader columnSchema={columnSchema} schema={schema} />,
        cell: ({ row }) => {
          const value = row.getValue(columnSchema.name);
          if ("peer" in columnSchema) {
            return (
              <TableCell>
                <TableRelationshipCell relationshipSchema={columnSchema} relationshipData={value} />
              </TableCell>
            );
          }
          return (
            <TableCell>
              <TableAttributeCell attributeSchema={columnSchema} attributeData={value} />
            </TableCell>
          );
        },
      };
    }),
  ];
};
