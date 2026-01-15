import type { PopoverTriggerProps } from "@radix-ui/react-popover";
import { type ColumnDef, createColumnHelper } from "@tanstack/react-table";

import { TableCell } from "@/shared/components/table/table-cell";
import { sortByOrderWeight } from "@/shared/utils/common";

import { IP_ADDRESS_AVAILABLE_KIND, IP_PREFIX_AVAILABLE_KIND } from "@/entities/ipam/constants";
import { KindBodyCell } from "@/entities/nodes/object/ui/object-table/cells/generics/kind-body-cell";
import { KindHeaderCell } from "@/entities/nodes/object/ui/object-table/cells/generics/kind-header-cell";
import { TableAttributeCell } from "@/entities/nodes/object/ui/object-table/cells/table-attribute-cell";
import { TableColumnHeader } from "@/entities/nodes/object/ui/object-table/cells/table-column-header";
import { TableIdentifierCell } from "@/entities/nodes/object/ui/object-table/cells/table-identifier-cell";
import { TableIdentifierHeader } from "@/entities/nodes/object/ui/object-table/cells/table-identifier-header";
import { TableRelationshipCell } from "@/entities/nodes/object/ui/object-table/cells/table-relationship-cell";
import { getToggleSelectedRowHandler } from "@/entities/nodes/object/ui/object-table/utils/get-toggle-selected-row-handler";
import { getAttributesVisibleInListView } from "@/entities/nodes/object/utils/get-attributes-visible-in-list-view";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list-view";
import type { NodeAttribute, NodeObject, NodeRelationship } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";

const columnHelper = createColumnHelper<NodeObject>();

export function getObjectIdentifierColumns(
  schema: ModelSchema
): Array<ColumnDef<NodeObject, string>> {
  return [
    columnHelper.accessor((node) => getNodeLabel(node), {
      id: "id",
      header: ({ table }) => {
        return (
          <TableIdentifierHeader
            schema={schema}
            isSelected={table.getIsAllRowsSelected()}
            isIndeterminate={table.getIsSomePageRowsSelected()}
            onChange={table.toggleAllRowsSelected}
          />
        );
      },
      cell: ({ cell, row, table }) => {
        const label = cell.getValue() ?? "-";

        return (
          <TableIdentifierCell
            objectKind={row.original.__typename}
            objectId={row.original.id}
            label={label}
            isSelected={row.getIsSelected()}
            onClickCheckbox={getToggleSelectedRowHandler({ row, table })}
          />
        );
      },
    }),
  ];
}

export function getObjectGenericColumns(schema: ModelSchema): Array<ColumnDef<NodeObject, string>> {
  return isGenericSchema(schema)
    ? [
        columnHelper.accessor("__typename", {
          id: "objectKind",
          header: () => {
            return <KindHeaderCell schema={schema} />;
          },
          cell: ({ cell }) => {
            const schemaKind = cell.getValue();
            if (schemaKind === IP_ADDRESS_AVAILABLE_KIND) return null;
            if (schemaKind === IP_PREFIX_AVAILABLE_KIND) return null;

            return <KindBodyCell schemaKind={schemaKind} />;
          },
        }),
      ]
    : [];
}

export function getObjectFieldsColumns(
  schema: ModelSchema,
  headerProps?: PopoverTriggerProps
): Array<ColumnDef<NodeObject, NodeAttribute | NodeRelationship>> {
  const attributes = getAttributesVisibleInListView(schema.attributes ?? []);
  const relationships = getRelationshipsVisibleInListView(schema.relationships ?? []);
  const sortedColumns = sortByOrderWeight([...attributes, ...relationships]);

  return sortedColumns.map((columnSchema) => {
    return columnHelper.accessor(columnSchema.name, {
      header: () => {
        return <TableColumnHeader columnSchema={columnSchema} {...headerProps} />;
      },
      cell: ({ cell }) => {
        const value = cell.getValue();
        if ("peer" in columnSchema) {
          return (
            <TableCell>
              <TableRelationshipCell
                relationshipSchema={columnSchema}
                relationshipData={value as NodeRelationship}
              />
            </TableCell>
          );
        }
        return (
          <TableCell>
            <TableAttributeCell
              attributeSchema={columnSchema}
              attributeData={value as NodeAttribute}
            />
          </TableCell>
        );
      },
    });
  });
}

export const getObjectTableColumns = (
  schema: ModelSchema,
  headerProps?: PopoverTriggerProps
): Array<ColumnDef<NodeObject>> => {
  return [
    ...getObjectIdentifierColumns(schema),
    ...getObjectGenericColumns(schema),
    ...getObjectFieldsColumns(schema, headerProps),
  ] as Array<ColumnDef<NodeObject>>;
};
