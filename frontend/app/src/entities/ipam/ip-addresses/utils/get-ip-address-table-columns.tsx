import { IP_ADDRESS_AVAILABLE_KIND } from "@/entities/ipam/constants";
import { IpAddressAvailableNode } from "@/entities/ipam/ip-addresses/domain/types";
import { IpAddressAvailableCreateFormTrigger } from "@/entities/ipam/ip-addresses/ui/ip-address-available-create-form-trigger";
import { getIpAddressAttributesVisibleInListView } from "@/entities/ipam/ip-addresses/utils/get-ip-address-attributes-visible-in-list-view";
import { getIpAddressRelationshipsVisibleInListView } from "@/entities/ipam/ip-addresses/utils/get-ip-address-relationships-visible-in-list-view";
import { KindBodyCell } from "@/entities/nodes/object/ui/object-table/cells/generics/kind-body-cell";
import { KindHeaderCell } from "@/entities/nodes/object/ui/object-table/cells/generics/kind-header-cell";
import { StickyLeftCell } from "@/entities/nodes/object/ui/object-table/cells/style";
import { TableAttributeCell } from "@/entities/nodes/object/ui/object-table/cells/table-attribute-cell";
import { TableColumnHeader } from "@/entities/nodes/object/ui/object-table/cells/table-column-header";
import { TableIdentifierCell } from "@/entities/nodes/object/ui/object-table/cells/table-identifier-cell";
import { TableRelationshipCell } from "@/entities/nodes/object/ui/object-table/cells/table-relationship-cell";
import { NodeAttribute, NodeCore, NodeObject, NodeRelationship } from "@/entities/nodes/types";
import { ModelSchema } from "@/entities/schema/types";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";
import { cellHeaderStyle, cellMutedStyle, cellsStyle } from "@/shared/components/table/style";
import { TableCell } from "@/shared/components/table/table-cell";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { PopoverTriggerProps } from "@radix-ui/react-popover";
import { ColumnDef, createColumnHelper } from "@tanstack/react-table";

const columnHelper = createColumnHelper<NodeObject | IpAddressAvailableNode>();

export const getIpAddressTableColumns = (
  schema: ModelSchema,
  headerProps?: PopoverTriggerProps
): ColumnDef<NodeCore>[] => {
  const attributes = getIpAddressAttributesVisibleInListView(schema.attributes ?? []);
  const relationships = getIpAddressRelationshipsVisibleInListView(schema.relationships ?? []);

  return [
    columnHelper.accessor("display_label", {
      id: "id",
      header: () => (
        <div className={classNames(cellsStyle, cellHeaderStyle, "left-0 z-10 hover:bg-white")}>
          {schema.icon && <Icon icon={schema.icon} className="text-stone-400" />}
          <span className="truncate">{schema.label}</span>
        </div>
      ),
      cell: ({ cell, row }) => {
        const displayLabel: string = cell.getValue() ?? "-";

        if (row.original.__typename === IP_ADDRESS_AVAILABLE_KIND) {
          const ipAddressAvailableNode = row.original as IpAddressAvailableNode;

          return (
            <>
              <StickyLeftCell isMuted className="p-0.5" data-testid="ip-address-available">
                <IpAddressAvailableCreateFormTrigger
                  ipAddressAvailableNode={ipAddressAvailableNode}
                />
              </StickyLeftCell>

              <TableCell className={classNames(cellMutedStyle, "col-start-2 -col-end-2")}>
                {displayLabel}
              </TableCell>
            </>
          );
        }

        return (
          <TableIdentifierCell
            objectKind={row.original.__typename as string}
            objectId={row.original.id as string}
            label={displayLabel}
            isSelected={row.getIsSelected()}
            onSelectionChange={row.getToggleSelectedHandler()}
          />
        );
      },
    }),
    ...(isGenericSchema(schema)
      ? [
          columnHelper.accessor("__typename", {
            id: "objectKind",
            header: () => <KindHeaderCell schema={schema} />,
            cell: ({ cell }) => <KindBodyCell schemaKind={cell.getValue()} />,
          }),
        ]
      : ([] as Array<any>)),
    ...attributes.map((attribute) => {
      return columnHelper.accessor(attribute.name, {
        header: () => (
          <TableColumnHeader columnSchema={attribute} schema={schema} {...headerProps} />
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
          <TableColumnHeader columnSchema={relationship} schema={schema} {...headerProps} />
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
  ];
};
