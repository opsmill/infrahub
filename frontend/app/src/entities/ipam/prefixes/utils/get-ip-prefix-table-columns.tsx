import { KindBodyCell } from "@/entities/nodes/object/ui/object-table/cells/generics/kind-body-cell";
import { KindHeaderCell } from "@/entities/nodes/object/ui/object-table/cells/generics/kind-header-cell";
import { TableAttributeCell } from "@/entities/nodes/object/ui/object-table/cells/table-attribute-cell";
import { TableColumnHeader } from "@/entities/nodes/object/ui/object-table/cells/table-column-header";
import { TableIdentifierCell } from "@/entities/nodes/object/ui/object-table/cells/table-identifier-cell";
import { TableRelationshipCell } from "@/entities/nodes/object/ui/object-table/cells/table-relationship-cell";
import { getAttributesVisibleInListView } from "@/entities/nodes/object/utils/get-attributes-visible-in-list-view";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list-view";
import { NodeObject } from "@/entities/nodes/types";
import { ModelSchema } from "@/entities/schema/types";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";
import ProgressBarChart from "@/shared/components/stats/progress-bar-chart";
import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { TableCell } from "@/shared/components/table/table-cell";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { PopoverTriggerProps } from "@radix-ui/react-popover";
import { ColumnDef } from "@tanstack/react-table";

export const getIpPrefixTableColumns = (
  schema: ModelSchema,
  headerProps?: PopoverTriggerProps
): ColumnDef<NodeObject>[] => {
  const attributes = getAttributesVisibleInListView(
    schema.attributes?.filter((attribute) =>
      ["description", "member_type", "utilization"].includes(attribute.name)
    ) ?? []
  );
  const relationships = getRelationshipsVisibleInListView(schema.relationships ?? []);

  return [
    {
      id: "id",
      accessorFn: (node) => node.display_label,
      header: () => (
        <div className={classNames(cellsStyle, cellHeaderStyle, "left-0 z-10 hover:bg-white")}>
          {schema.icon && <Icon icon={schema.icon} className="text-stone-400" />}
          <span className="truncate">{schema.label}</span>
        </div>
      ),
      cell: ({ row }) => {
        const value: string = (row.getValue("id") ?? "-") as string;
        const ancestors: number = row.original.ancestors?.count ?? 0;
        return (
          <TableIdentifierCell
            objectKind={row.original.__typename as string}
            objectId={row.original.id as string}
            isSelected={row.getIsSelected()}
            onSelectionChange={row.getToggleSelectedHandler()}
            label={
              <>
                {[...Array(ancestors)].map((_, i) => (
                  <div className="bg-current size-1 rounded-full mr-2.5" key={i} />
                ))}
                {value}
              </>
            }
          />
        );
      },
    },
    ...(isGenericSchema(schema)
      ? [
          {
            id: "objectKind",
            accessorFn: (row) => row.__typename,
            header: () => <KindHeaderCell schema={schema} {...headerProps} />,
            cell: ({ cell }) => <KindBodyCell schemaKind={cell.getValue() as string} />,
          },
        ]
      : []),
    ...attributes.map((attribute) => {
      return {
        accessorKey: attribute.name,
        header: () => (
          <TableColumnHeader columnSchema={attribute} schema={schema} {...headerProps} />
        ),
        cell: ({ cell, row }) => {
          const attributeData = cell.getValue();

          if (attribute.name === "member_type") {
            const memberCount: number =
              attributeData.value === "prefix"
                ? (row.original.children as any).count
                : (row.original.ip_addresses as any).count;

            return (
              <TableCell className="whitespace-nowrap gap-3">
                <TableAttributeCell attributeSchema={attribute} attributeData={attributeData} />
                <div className="ml-auto text-xs">
                  <span>{memberCount}</span> <span className="text-gray-400">members</span>
                </div>
              </TableCell>
            );
          }
          if (attribute.name === "utilization") {
            return (
              <TableCell>
                <ProgressBarChart value={parseInt(attributeData.value, 10)} />
              </TableCell>
            );
          }

          return (
            <TableCell>
              <TableAttributeCell attributeSchema={attribute} attributeData={attributeData} />
            </TableCell>
          );
        },
      };
    }),
    ...relationships.map((relationship) => {
      return {
        accessorKey: relationship.name,
        header: () => (
          <TableColumnHeader columnSchema={relationship} schema={schema} {...headerProps} />
        ),
        cell: ({ cell }) => {
          const value = cell.getValue();

          return (
            <TableCell>
              <TableRelationshipCell relationshipSchema={relationship} relationshipData={value} />
            </TableCell>
          );
        },
      };
    }),
  ];
};
