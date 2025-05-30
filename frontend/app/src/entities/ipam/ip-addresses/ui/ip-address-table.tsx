import { getIpAddressTableColumns } from "@/entities/ipam/ip-addresses/utils/get-ip-address-table-columns";
import { useObjects } from "@/entities/nodes/object/domain/get-objects.query";
import { getObjectActionsColumn } from "@/entities/nodes/object/ui/object-table/get-object-actions-column";
import { ObjectsTableProps } from "@/entities/nodes/object/ui/object-table/object-table";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import useFilters, { Filter } from "@/shared/hooks/useFilters";
import React from "react";

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
    <InfiniteScroll scrollX hasNextPage={hasNextPage} onLoadMore={fetchNextPage}>
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
