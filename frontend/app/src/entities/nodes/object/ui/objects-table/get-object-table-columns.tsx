import { ColumnDef } from "@tanstack/react-table";
import * as R from "remeda";

import { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { ActionsCell } from "@/entities/nodes/object/ui/objects-table/cells/actions-cell";
import { KindBodyCell } from "@/entities/nodes/object/ui/objects-table/cells/generics/kind-body-cell";
import { KindHeaderCell } from "@/entities/nodes/object/ui/objects-table/cells/generics/kind-header-cell";
import { cellHeaderStyle, cellsStyle } from "@/entities/nodes/object/ui/objects-table/cells/style";
import { TableAttributeCell } from "@/entities/nodes/object/ui/objects-table/cells/table-attribute-cell";
import { TableCell } from "@/entities/nodes/object/ui/objects-table/cells/table-cell";
import { TableColumnHeader } from "@/entities/nodes/object/ui/objects-table/cells/table-column-header";
import { TableRelationshipCell } from "@/entities/nodes/object/ui/objects-table/cells/table-relationship-cell";
import { TableRowIdentifier } from "@/entities/nodes/object/ui/objects-table/cells/table-row-identifier";
import { getAttributesVisibleInListView } from "@/entities/nodes/object/utils/get-attributes-visible-in-list";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list";
import { Permission } from "@/entities/permission/types";
import { IModelSchema } from "@/entities/schema/stores/schema.atom";
import { isGenericSchema } from "@/entities/schema/utils";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";

export const getObjectTableColumns = (
  schema: IModelSchema,
  permission: Permission
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
        <div className={classNames(cellsStyle, cellHeaderStyle, "left-0 z-10 hover:bg-white")}>
          {schema.icon && <Icon icon={schema.icon} className="text-stone-400" />}
          <span className="truncate">{schema.label}</span>
        </div>
      ),
      cell: ({ row }) => {
        const value = (row.getValue("id") ?? "-") as string;
        return (
          <TableRowIdentifier
            objectKind={row.original.__typename as string}
            objectId={row.original.id as string}
            identifier={value}
          />
        );
      },
    },
    ...(isGenericSchema(schema)
      ? [
          {
            id: "kind",
            accessorFn: (row) => row.__typename,
            header: () => <KindHeaderCell schema={schema} />,
            cell: ({ cell }) => <KindBodyCell schemaKind={cell.getValue() as string} />,
          },
        ]
      : []),
    ...sortedColumns.map((columnSchema) => {
      return {
        accessorKey: columnSchema.name,
        header: () => <TableColumnHeader columnSchema={columnSchema} schema={schema} />,
        cell: ({ cell }) => {
          const value = cell.getValue();
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
    {
      id: "actions",
      header: () => (
        <div
          className={classNames(
            cellsStyle,
            cellHeaderStyle,
            "right-0 z-10 border-l size-10 -ml-px hover:bg-white"
          )}
        />
      ),
      cell: ({ row }) => {
        return (
          <ActionsCell
            permission={permission}
            objectKind={row.original.__typename as string}
            objectLabel={row.getValue("id") as string}
            objectId={row.original.id as string}
          />
        );
      },
    },
  ];
};
