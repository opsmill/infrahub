import ErrorScreen from "@/shared/components/errors/error-screen";
import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import type { Filter } from "@/shared/hooks/useFilters";

import { IP_ADDRESS_AVAILABLE_KIND } from "@/entities/ipam/constants";
import { useGetIpAddressList } from "@/entities/ipam/ip-addresses/ui/queries/get-ip-address-list.query";
import { getIpAddressTableColumns } from "@/entities/ipam/ip-addresses/utils/get-ip-address-table-columns";
import { useObjectsCount } from "@/entities/nodes/object/domain/get-objects-count.query";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import { getObjectActionsColumn } from "@/entities/nodes/object/ui/object-table/utils/get-object-actions-column";

const IP_ADDRESS_TABLE_COLUMN_ORDER = ["id", "objectKind", "ip_prefix", "description"];

export interface IpAddressTableProps {
  baseFilters?: Array<Filter>;
}

export function IpAddressTable({ baseFilters = [] }: IpAddressTableProps) {
  const { filters, selectedSchema, permission } = useObjectTableContext();
  const allFilters = [...baseFilters, ...filters];

  const { data: count } = useObjectsCount({
    objectKind: selectedSchema.kind!,
    filters: allFilters,
  });

  const { isPending, isFetchingNextPage, data, error, fetchNextPage, hasNextPage } =
    useGetIpAddressList({
      schema: selectedSchema,
      filters: allFilters,
    });

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const columns = [...getIpAddressTableColumns(selectedSchema), getObjectActionsColumn(permission)];
  const flatData = data?.pages?.flat() ?? [];

  return (
    <InfiniteScroll scrollX hasNextPage={hasNextPage} onLoadMore={fetchNextPage}>
      <DataTable
        columnOrder={IP_ADDRESS_TABLE_COLUMN_ORDER}
        columns={columns}
        count={count}
        data={flatData}
        enableRowSelection={(row) => row.original.__typename !== IP_ADDRESS_AVAILABLE_KIND}
        isLoading={isPending || isFetchingNextPage}
        renderEmpty={() => <ObjectTableEmpty schema={selectedSchema} />}
        data-testid="ip-address-table"
      />
    </InfiniteScroll>
  );
}
