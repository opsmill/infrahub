import React from "react";

import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import { Filter } from "@/shared/hooks/useFilters";

import { useGetIpPrefixList } from "@/entities/ipam/ip-prefixes/domain/get-ip-prefix-list.query";
import { getIpPrefixTableColumns } from "@/entities/ipam/ip-prefixes/utils/get-ip-prefix-table-columns";
import { getObjectActionsColumn } from "@/entities/nodes/object/ui/object-table/get-object-actions-column";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";

const IP_PREFIX_TABLE_COLUMN_ORDER = [
  "id",
  "objectKind",
  "member_type",
  "member_count",
  "utilization",
  "parent",
  "description",
];

export interface IpPrefixTableProps {
  baseFilters?: Array<Filter>;
}

export function IpPrefixTable({ baseFilters = [] }: IpPrefixTableProps) {
  const { filters, selectedSchema, permission } = useObjectTableContext();

  const { data, fetchNextPage, hasNextPage, isPending, isFetchingNextPage } = useGetIpPrefixList({
    schema: selectedSchema,
    filters: [...baseFilters, ...filters],
  });

  const columns = React.useMemo(() => {
    return [...getIpPrefixTableColumns(selectedSchema), getObjectActionsColumn(permission)];
  }, [selectedSchema.hash, permission]);

  const flatData = React.useMemo(() => data?.pages?.flat() ?? [], [data]);

  return (
    <InfiniteScroll scrollX hasNextPage={hasNextPage} onLoadMore={fetchNextPage}>
      <DataTable
        columnOrder={IP_PREFIX_TABLE_COLUMN_ORDER}
        columns={columns}
        data={flatData}
        isLoading={isPending || isFetchingNextPage}
        renderEmpty={() => <ObjectTableEmpty schema={selectedSchema} />}
        data-testid="ip-prefix-table"
      />
    </InfiniteScroll>
  );
}
