import { type ColumnDef, createColumnHelper } from "@tanstack/react-table";

import { cellMutedStyle } from "@/shared/components/table/style";
import { TableCell } from "@/shared/components/table/table-cell";
import { classNames } from "@/shared/utils/common";

import type { IpAddressAvailableNode } from "@/entities/ipam/ip-addresses/domain/model/ip-address";
import { IP_ADDRESS_AVAILABLE_KIND } from "@/entities/ipam/ip-addresses/domain/model/ip-address";
import { getIpAddressAttributesVisibleInListView } from "@/entities/ipam/ip-addresses/domain/rules/get-ip-address-attributes-visible-in-list-view";
import { getIpAddressRelationshipsVisibleInListView } from "@/entities/ipam/ip-addresses/domain/rules/get-ip-address-relationships-visible-in-list-view";
import { IpAddressAvailableCreateFormTrigger } from "@/entities/ipam/ip-addresses/ui/ip-address-available-create-form-trigger";
import type {
  NodeAttribute,
  NodeObject,
  NodeRelationship,
} from "@/entities/nodes/object/domain/model/node";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import { StickyLeftCell } from "@/entities/nodes/object/ui/object-table/cells/style";
import { TableAttributeCell } from "@/entities/nodes/object/ui/object-table/cells/table-attribute-cell";
import {
  TableColumnHeader,
  type TableColumnHeaderProps,
} from "@/entities/nodes/object/ui/object-table/cells/table-column-header";
import { TableIdentifierCell } from "@/entities/nodes/object/ui/object-table/cells/table-identifier-cell";
import { TableIdentifierHeader } from "@/entities/nodes/object/ui/object-table/cells/table-identifier-header";
import { TableRelationshipCell } from "@/entities/nodes/object/ui/object-table/cells/table-relationship-cell";
import { getObjectGenericColumns } from "@/entities/nodes/object/ui/object-table/utils/get-object-table-columns";
import { getToggleSelectedRowHandler } from "@/entities/nodes/object/ui/object-table/utils/get-toggle-selected-row-handler";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

const columnHelper = createColumnHelper<NodeObject | IpAddressAvailableNode>();

export const getIpAddressTableColumns = (
  schema: ModelSchema,
  headerProps?: Partial<TableColumnHeaderProps>
): ColumnDef<NodeObject>[] => {
  const attributes = getIpAddressAttributesVisibleInListView(schema.attributes ?? []);
  const relationships = getIpAddressRelationshipsVisibleInListView(schema.relationships ?? []);

  return [
    columnHelper.accessor("display_label", {
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
      cell: ({ row, table }) => {
        const value: string = getNodeLabel(row.original) ?? "-";
        const ipAdressNode = row.original;

        if (ipAdressNode.__typename === IP_ADDRESS_AVAILABLE_KIND) {
          const ipAddressAvailableNode = ipAdressNode as IpAddressAvailableNode;

          return (
            <>
              <StickyLeftCell isMuted className="p-0.5" data-testid="ip-address-available">
                <IpAddressAvailableCreateFormTrigger
                  ipAddressAvailableNode={ipAddressAvailableNode}
                />
              </StickyLeftCell>

              <TableCell className={classNames(cellMutedStyle, "col-start-2 -col-end-2")}>
                {ipAdressNode.display_label}
              </TableCell>
            </>
          );
        }

        return (
          <TableIdentifierCell
            objectKind={ipAdressNode.__typename as string}
            objectId={ipAdressNode.id as string}
            label={value}
            isSelected={row.getIsSelected()}
            onClickCheckbox={getToggleSelectedRowHandler({ row, table })}
          />
        );
      },
    }),
    ...getObjectGenericColumns(schema),
    ...attributes.map((attribute) => {
      return columnHelper.accessor(attribute.name, {
        header: () => (
          <TableColumnHeader schema={schema} columnSchema={attribute} {...headerProps} />
        ),
        cell: ({ cell, row }) => {
          const attributeData = cell.getValue() as NodeAttribute | undefined;
          if (!attributeData) return null;
          if (row.original.__typename === IP_ADDRESS_AVAILABLE_KIND) return null; // no columns for ip range availability rows

          return (
            <TableCell>
              <TableAttributeCell attributeSchema={attribute} attributeData={attributeData} />
            </TableCell>
          );
        },
      });
    }),
    ...relationships.map((relationship) => {
      return columnHelper.accessor(relationship.name, {
        header: () => (
          <TableColumnHeader schema={schema} columnSchema={relationship} {...headerProps} />
        ),
        cell: ({ cell, row }) => {
          const relationshipData = cell.getValue() as NodeRelationship | undefined;
          if (!relationshipData) return null;
          if (row.original.__typename === IP_ADDRESS_AVAILABLE_KIND) return null; // no columns for ip range availability rows

          return (
            <TableCell>
              <TableRelationshipCell
                relationshipSchema={relationship}
                relationshipData={relationshipData}
              />
            </TableCell>
          );
        },
      });
    }),
  ] as ColumnDef<NodeObject>[];
};
