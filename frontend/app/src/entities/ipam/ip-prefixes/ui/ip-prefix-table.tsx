import ErrorScreen from "@/shared/components/errors/error-screen";
import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";

import { IP_PREFIX_AVAILABLE_KIND } from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix";
import { getIpPrefixTableColumns } from "@/entities/ipam/ip-prefixes/ui/get-ip-prefix-table-columns";
import { useGetIpPrefixList } from "@/entities/ipam/ip-prefixes/ui/queries/get-ip-prefix-list.query";
import { useColumnVisibility } from "@/entities/nodes/columns/ui/hooks/use-column-visibility";
import type { Filter } from "@/entities/nodes/filters/domain/model/filter";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import { getObjectActionsColumn } from "@/entities/nodes/object/ui/object-table/utils/get-object-actions-column";
import { useObjectsCount } from "@/entities/nodes/object/ui/queries/get-objects-count.query";
import { useSort } from "@/entities/nodes/sort/ui/hooks/use-sort";

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
  const { filters, selectedSchema, permission, columnSurface } = useObjectTableContext();
  const { customSort } = useSort(selectedSchema);
  const { columnVisibility } = useColumnVisibility(selectedSchema, columnSurface);
  const allFilters = [...baseFilters, ...filters];

  const { data: count } = useObjectsCount({
    objectKind: selectedSchema.kind!,
    filters: allFilters,
  });

  const { data, fetchNextPage, error, hasNextPage, isPending, isFetchingNextPage } =
    useGetIpPrefixList({
      schema: selectedSchema,
      filters: allFilters,
      sort: customSort,
    });

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const columns = [...getIpPrefixTableColumns(selectedSchema), getObjectActionsColumn(permission)];
  const flatData = data?.pages?.flat() ?? [];

  return (
    <InfiniteScroll scrollX hasNextPage={hasNextPage} onLoadMore={fetchNextPage}>
      <DataTable
        columnOrder={IP_PREFIX_TABLE_COLUMN_ORDER}
        columnVisibility={columnVisibility}
        columns={columns}
        count={count}
        data={flatData}
        enableRowSelection={(row) => row.original.__typename !== IP_PREFIX_AVAILABLE_KIND}
        isLoading={isPending || isFetchingNextPage}
        renderEmpty={() => <ObjectTableEmpty schema={selectedSchema} />}
        data-testid="ip-prefix-table"
      />
    </InfiniteScroll>
  );
}
