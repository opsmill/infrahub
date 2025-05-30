import { useGetIpPrefixList } from "@/entities/ipam/ip-prefixes/domain/get-ip-prefix-list.query";
import { getIpPrefixTableColumns } from "@/entities/ipam/ip-prefixes/utils/get-ip-prefix-table-columns";
import { getObjectActionsColumn } from "@/entities/nodes/object/ui/object-table/get-object-actions-column";
import { ObjectsTableProps } from "@/entities/nodes/object/ui/object-table/object-table";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import useFilters, { Filter } from "@/shared/hooks/useFilters";
import React from "react";

const IP_PREFIX_TABLE_COLUMN_ORDER = [
  "id",
  "objectKind",
  "member_type",
  "member_count",
  "utilization",
  "parent",
  "description",
];

export interface IpPrefixTableProps extends ObjectsTableProps {
  baseFilters?: Array<Filter>;
}

export function IpPrefixTable({ schema, permission, baseFilters = [] }: IpPrefixTableProps) {
  const [filters] = useFilters();
  const { data, fetchNextPage, hasNextPage, isPending, isFetchingNextPage } = useGetIpPrefixList({
    schema,
    filters: [...baseFilters, ...filters],
  });

  const columns = React.useMemo(() => {
    return [...getIpPrefixTableColumns(schema), getObjectActionsColumn(permission)];
  }, [schema.hash]);
  const flatData = React.useMemo(() => data?.pages?.flat() ?? [], [data]);

  return (
    <InfiniteScroll scrollX hasNextPage={hasNextPage} onLoadMore={fetchNextPage}>
      <DataTable
        columnOrder={IP_PREFIX_TABLE_COLUMN_ORDER}
        columns={columns}
        data={flatData}
        isLoading={isPending || isFetchingNextPage}
        renderEmpty={() => <ObjectTableEmpty schema={schema} />}
        data-testid="ip-prefix-table"
      />
    </InfiniteScroll>
  );
}
