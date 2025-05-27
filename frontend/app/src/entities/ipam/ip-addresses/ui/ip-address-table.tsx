import { useObjects } from "@/entities/nodes/object/domain/get-objects.query";
import { KindBodyCell } from "@/entities/nodes/object/ui/object-table/cells/generics/kind-body-cell";
import { KindHeaderCell } from "@/entities/nodes/object/ui/object-table/cells/generics/kind-header-cell";
import { TableAttributeCell } from "@/entities/nodes/object/ui/object-table/cells/table-attribute-cell";
import { TableColumnHeader } from "@/entities/nodes/object/ui/object-table/cells/table-column-header";
import { TableIdentifierCell } from "@/entities/nodes/object/ui/object-table/cells/table-identifier-cell";
import { TableRelationshipCell } from "@/entities/nodes/object/ui/object-table/cells/table-relationship-cell";
import { getObjectActionsColumn } from "@/entities/nodes/object/ui/object-table/get-object-actions-column";
import { ObjectsTableProps } from "@/entities/nodes/object/ui/object-table/object-table";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import { getAttributesVisibleInListView } from "@/entities/nodes/object/utils/get-attributes-visible-in-list-view";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { getRelationshipsVisibleInListView } from "@/entities/nodes/object/utils/get-relationships-visible-in-list-view";
import { NodeObject } from "@/entities/nodes/types";
import { ModelSchema } from "@/entities/schema/types";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";
import ProgressBarChart from "@/shared/components/stats/progress-bar-chart";
import { DataTable } from "@/shared/components/table/data-table";
import { cellHeaderStyle, cellsStyle } from "@/shared/components/table/style";
import { TableCell } from "@/shared/components/table/table-cell";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import useFilters, { Filter } from "@/shared/hooks/useFilters";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { PopoverTriggerProps } from "@radix-ui/react-popover";
import { ColumnDef } from "@tanstack/react-table";
import React from "react";

export const getIpAddressTableColumns = (
  schema: ModelSchema,
  headerProps?: PopoverTriggerProps
): ColumnDef<NodeObject>[] => {
  const attributes = getAttributesVisibleInListView(
    schema.attributes?.filter((attribute) => !["address"].includes(attribute.name)) ?? []
  );
  const relationships = [
    schema.relationships?.find((relationship) => relationship.name === "ip_prefix"),
    ...getRelationshipsVisibleInListView(schema.relationships ?? []),
  ];

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
            isSelected={row.getIsSelected()}
            onSelectionChange={row.getToggleSelectedHandler()}
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
        cell: ({ cell }) => {
          const value = cell.getValue();

          if (attribute.name === "utilization") {
            return (
              <TableCell>
                <ProgressBarChart value={parseInt(value.value, 10)} />
              </TableCell>
            );
          }

          return (
            <TableCell>
              <TableAttributeCell attributeSchema={attribute} attributeData={value} />
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

const IP_ADDRESS_TABLE_COLUMN_ORDER = ["id", "objectKind", "ip_prefix", "description"];

export interface IpAddressTableProps extends ObjectsTableProps {
  baseFilters?: Array<Filter>;
}

export function IpAddressTable({ schema, permission, baseFilters = [] }: IpAddressTableProps) {
  const [filters] = useFilters();
  const { isPending, isFetchingNextPage, data, fetchNextPage, hasNextPage } = useObjects({
    schema,
    filters: [...baseFilters, ...filters],
    getAttributesVisible: (attributes) =>
      attributes.filter((attribute) => !["address"].includes(attribute.name)),
    getRelationshipsVisible: (relationships) =>
      relationships.filter((relationship) => relationship.name === "ip_prefix"),
  });

  const columns = React.useMemo(() => {
    return [...getIpAddressTableColumns(schema), getObjectActionsColumn(permission)];
  }, [schema.hash]);
  const flatData = React.useMemo(() => data?.pages?.flat() ?? [], [data]);

  return (
    <InfiniteScroll hasNextPage={hasNextPage} onLoadMore={fetchNextPage}>
      <DataTable
        columnOrder={IP_ADDRESS_TABLE_COLUMN_ORDER}
        columns={columns}
        data={flatData}
        isLoading={isPending || isFetchingNextPage}
        renderEmpty={() => <ObjectTableEmpty schema={schema} />}
      />
    </InfiniteScroll>
  );
}
