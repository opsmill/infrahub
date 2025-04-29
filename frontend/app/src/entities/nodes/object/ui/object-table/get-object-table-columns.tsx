import { KindBodyCell } from "@/entities/nodes/object/ui/object-table/cells/generics/kind-body-cell";
import { KindHeaderCell } from "@/entities/nodes/object/ui/object-table/cells/generics/kind-header-cell";
import { TableAttributeCell } from "@/entities/nodes/object/ui/object-table/cells/table-attribute-cell";
import { TableColumnHeader } from "@/entities/nodes/object/ui/object-table/cells/table-column-header";
import { TableIdentifierCell } from "@/entities/nodes/object/ui/object-table/cells/table-identifier-cell";
import { TableRelationshipCell } from "@/entities/nodes/object/ui/object-table/cells/table-relationship-cell";
import { getAttributesVisibleInListView } from "@/entities/nodes/object/utils/get-attributes-visible-in-list-view";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list-view";
import { NodeObject } from "@/entities/nodes/types";
import { ModelSchema } from "@/entities/schema/types";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";
import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { TableCell } from "@/shared/components/table/table-cell";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { PopoverTriggerProps } from "@radix-ui/react-popover";
import { ColumnDef } from "@tanstack/react-table";
import * as R from "remeda";

export const getObjectTableColumns = (
  schema: ModelSchema,
  headerProps?: PopoverTriggerProps
): ColumnDef<NodeObject>[] => {
  const attributes = getAttributesVisibleInListView(schema.attributes ?? []);
  const relationships = getRelationshipsVisibleInListView(schema.relationships ?? []);
  const sortedColumns = R.pipe(
    [...attributes, ...relationships],
    R.sortBy((column) => column.order_weight ?? 0)
  );

  return [
    {
      id: "id",
      accessorFn: (node) => getNodeLabel(node),
      header: () => (
        <div className={classNames(cellsStyle, cellHeaderStyle, "left-0 z-10 hover:bg-white")}>
          {schema.icon && <Icon icon={schema.icon} className="text-stone-400" />}
          <span className="truncate">{schema.label}</span>
        </div>
      ),
      cell: ({ row }) => {
        const value = (row.getValue("id") ?? "-") as string;
        return (
          <TableIdentifierCell
            objectKind={row.original.__typename as string}
            objectId={row.original.id as string}
            label={value}
          />
        );
      },
    },
    ...(isGenericSchema(schema)
      ? [
          {
            id: "__typename",
            accessorFn: (row) => row.__typename,
            header: () => <KindHeaderCell schema={schema} {...headerProps} />,
            cell: ({ cell }) => <KindBodyCell schemaKind={cell.getValue() as string} />,
          },
        ]
      : []),
    ...sortedColumns.map((columnSchema) => {
      return {
        accessorKey: columnSchema.name,
        header: () => (
          <TableColumnHeader columnSchema={columnSchema} schema={schema} {...headerProps} />
        ),
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
  ];
};
