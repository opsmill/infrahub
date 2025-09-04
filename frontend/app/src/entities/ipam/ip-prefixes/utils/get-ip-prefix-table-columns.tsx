import { Icon } from "@iconify-icon/react";
import { ColumnDef, createColumnHelper } from "@tanstack/react-table";

import { Row } from "@/shared/components/container";
import ProgressBarChart from "@/shared/components/stats/progress-bar-chart";
import { cellHeaderStyle, cellMutedStyle, cellsStyle } from "@/shared/components/table/style";
import { TableCell } from "@/shared/components/table/table-cell";
import { classNames } from "@/shared/utils/common";
import { pluralize } from "@/shared/utils/string";

import { IP_PREFIX_AVAILABLE_KIND } from "@/entities/ipam/constants";
import { IpPrefixNode } from "@/entities/ipam/ip-prefixes/types";
import { IpPrefixAvailableIdentifier } from "@/entities/ipam/ip-prefixes/ui/ip-prefix-available-identifier";
import { getPrefixAttributesVisibleInListView } from "@/entities/ipam/ip-prefixes/utils/get-prefix-attributes-visible-in-list-view";
import { StickyLeftCell } from "@/entities/nodes/object/ui/object-table/cells/style";
import { TableAttributeCell } from "@/entities/nodes/object/ui/object-table/cells/table-attribute-cell";
import { TableColumnHeader } from "@/entities/nodes/object/ui/object-table/cells/table-column-header";
import { TableIdentifierCell } from "@/entities/nodes/object/ui/object-table/cells/table-identifier-cell";
import { TableRelationshipCell } from "@/entities/nodes/object/ui/object-table/cells/table-relationship-cell";
import { getObjectGenericColumns } from "@/entities/nodes/object/ui/object-table/get-object-table-columns";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list-view";
import { NodeAttribute, NodeObject, NodeRelationship } from "@/entities/nodes/types";
import { ModelSchema } from "@/entities/schema/types";

const columnHelper = createColumnHelper<IpPrefixNode>();

export const getIpPrefixTableColumns = (schema: ModelSchema): Array<ColumnDef<NodeObject>> => {
  const attributes = getPrefixAttributesVisibleInListView(schema.attributes ?? []);
  const relationships = getRelationshipsVisibleInListView(schema.relationships ?? []);

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
        const value: string = cell.getValue() ?? "-";
        const ipPrefixNode = row.original;

        if (ipPrefixNode.__typename === IP_PREFIX_AVAILABLE_KIND) {
          return (
            <>
              <StickyLeftCell isMuted className="pl-0.5" data-testid="ip-prefix-available">
                <IpPrefixAvailableIdentifier ipPrefixNode={row.original} />
              </StickyLeftCell>

              <TableCell className={classNames(cellMutedStyle, "col-start-2 -col-end-2")}>
                {schema.label} available
              </TableCell>
            </>
          );
        }

        return (
          <TableIdentifierCell
            objectKind={ipPrefixNode.__typename as string}
            objectId={ipPrefixNode.id as string}
            isSelected={row.getIsSelected()}
            onSelectionChange={row.getToggleSelectedHandler()}
            label={
              <Row className="gap-2.5">
                {[...Array(ipPrefixNode.ancestors.count)].map((_, i) => (
                  <div className="bg-custom-blue-600/40 size-1 rounded-full" key={i} />
                ))}
                {value}
              </Row>
            }
          />
        );
      },
    }),
    ...getObjectGenericColumns(schema),
    ...attributes.map((attribute) => {
      return columnHelper.accessor(attribute.name, {
        header: () => <TableColumnHeader columnSchema={attribute} schema={schema} />,
        cell: ({ cell, row }) => {
          const attributeData = cell.getValue() as NodeAttribute | undefined;
          if (!attributeData) return null;
          if (row.original.__typename === IP_PREFIX_AVAILABLE_KIND) return null; // no columns for availability rows

          if (attribute.name === "member_type") {
            const memberCount: number =
              attributeData.value === "prefix"
                ? row.original.children.count
                : row.original.ip_addresses.count;

            return (
              <TableCell className="whitespace-nowrap gap-4">
                <TableAttributeCell attributeSchema={attribute} attributeData={attributeData} />
                <div className="ml-auto text-xs">
                  <span className="text-gray-400">{pluralize(memberCount, "member")}</span>
                </div>
              </TableCell>
            );
          }
          if (attribute.name === "utilization") {
            return (
              <TableCell className="w-40">
                <ProgressBarChart value={parseInt(attributeData.value as string, 10)} />
              </TableCell>
            );
          }

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
        header: () => <TableColumnHeader columnSchema={relationship} schema={schema} />,
        cell: ({ cell, row }) => {
          const relationshipData = cell.getValue() as NodeRelationship | undefined;
          if (!relationshipData) return null;
          if (row.original.__typename === IP_PREFIX_AVAILABLE_KIND) return null; // no columns for availability rows

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
  ] as Array<ColumnDef<NodeObject>>;
};
