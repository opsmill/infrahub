import { IP_ADDRESS_AVAILABLE_KIND, IP_PREFIX_AVAILABLE_KIND } from "@/entities/ipam/constants";
import { KindBodyCell } from "@/entities/nodes/object/ui/object-table/cells/generics/kind-body-cell";
import { KindHeaderCell } from "@/entities/nodes/object/ui/object-table/cells/generics/kind-header-cell";
import { TableAttributeCell } from "@/entities/nodes/object/ui/object-table/cells/table-attribute-cell";
import { TableColumnHeader } from "@/entities/nodes/object/ui/object-table/cells/table-column-header";
import { TableIdentifierCell } from "@/entities/nodes/object/ui/object-table/cells/table-identifier-cell";
import { TableRelationshipCell } from "@/entities/nodes/object/ui/object-table/cells/table-relationship-cell";
import { getAttributesVisibleInListView } from "@/entities/nodes/object/utils/get-attributes-visible-in-list-view";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list-view";
import { NodeAttribute, NodeObject, NodeRelationship } from "@/entities/nodes/types";
import { ModelSchema } from "@/entities/schema/types";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";
import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { TableCell } from "@/shared/components/table/table-cell";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { PopoverTriggerProps } from "@radix-ui/react-popover";
import { ColumnDef, createColumnHelper } from "@tanstack/react-table";
import * as R from "remeda";

const columnHelper = createColumnHelper<NodeObject>();

export function getObjectIdentifierColumns(
  schema: ModelSchema
): Array<ColumnDef<NodeObject, string>> {
  return [
    columnHelper.accessor((node) => getNodeLabel(node), {
      id: "id",
      header: () => (
        <div className={classNames(cellsStyle, cellHeaderStyle, "left-0 z-10 hover:bg-white")}>
          {schema.icon && <Icon icon={schema.icon} className="text-stone-400" />}
          <span className="truncate">{schema.label}</span>
        </div>
      ),
      cell: ({ cell, row }) => {
        const value: string = cell.getValue() ?? "-";

        return (
          <TableIdentifierCell
            objectKind={row.original.__typename as string}
            objectId={row.original.id as string}
            label={value}
            isSelected={row.getIsSelected()}
            onSelectionChange={row.getToggleSelectedHandler()}
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
  const sortedColumns = R.pipe(
    [...attributes, ...relationships],
    R.sortBy((column) => column.order_weight ?? 0)
  );

  return sortedColumns.map((columnSchema) => {
    return columnHelper.accessor(columnSchema.name, {
      header: () => {
        return <TableColumnHeader columnSchema={columnSchema} schema={schema} {...headerProps} />;
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
