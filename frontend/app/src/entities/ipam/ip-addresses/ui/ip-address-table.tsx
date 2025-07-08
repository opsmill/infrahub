import { getIpAddressTableColumns } from "@/entities/ipam/ip-addresses/utils/get-ip-address-table-columns";
import { useObjects } from "@/entities/nodes/object/domain/get-objects.query";
import { getObjectActionsColumn } from "@/entities/nodes/object/ui/object-table/get-object-actions-column";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import { Filter } from "@/shared/hooks/useFilters";
import React from "react";

const IP_ADDRESS_TABLE_COLUMN_ORDER = ["id", "objectKind", "ip_prefix", "description"];

export interface IpAddressTableProps {
  baseFilters?: Array<Filter>;
}

export function IpAddressTable({ baseFilters = [] }: IpAddressTableProps) {
  const { filters, selectedSchema, permission } = useObjectTableContext();
  const { isPending, isFetchingNextPage, data, fetchNextPage, hasNextPage } = useObjects({
    schema: selectedSchema,
    filters: [...baseFilters, ...filters],
    getAttributesVisible: (attributes) =>
      attributes.filter((attribute) => !["address"].includes(attribute.name)),
    getRelationshipsVisible: (relationships) =>
      relationships.filter((relationship) => relationship.name === "ip_prefix"),
  });

  const columns = React.useMemo(() => {
    return [...getIpAddressTableColumns(selectedSchema), getObjectActionsColumn(permission)];
  }, [selectedSchema.hash]);
  const flatData = React.useMemo(() => data?.pages?.flat() ?? [], [data]);

  return (
    <InfiniteScroll scrollX hasNextPage={hasNextPage} onLoadMore={fetchNextPage}>
      <DataTable
        columnOrder={IP_ADDRESS_TABLE_COLUMN_ORDER}
        columns={columns}
        data={flatData}
        isLoading={isPending || isFetchingNextPage}
        renderEmpty={() => <ObjectTableEmpty schema={selectedSchema} />}
      />
    </InfiniteScroll>
  );
}
