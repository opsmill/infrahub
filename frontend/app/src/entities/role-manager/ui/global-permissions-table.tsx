import ErrorScreen from "@/shared/components/errors/error-screen";
import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import type { Filter } from "@/shared/hooks/useFilters";

import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import { getObjectActionsColumn } from "@/entities/nodes/object/ui/object-table/utils/get-object-actions-column";
import { useObjects } from "@/entities/nodes/object/ui/queries/get-objects.query";
import { useObjectsCount } from "@/entities/nodes/object/ui/queries/get-objects-count.query";
import { getDecisionNumericValue } from "@/entities/role-manager/constants";
import {
  GLOBAL_PERMISSIONS_TABLE_ATTRIBUTES,
  GLOBAL_PERMISSIONS_TABLE_RELATIONSHIPS,
  getGlobalPermissionsTableColumns,
} from "@/entities/role-manager/ui/get-global-permissions-table-columns";

export function resolveDecisionFilters(filters: Filter[]): Filter[] {
  return filters.map((filter) => {
    if (filter.name === "decision__value") {
      return { ...filter, value: getDecisionNumericValue(filter.value) };
    }
    return filter;
  });
}

export function GlobalPermissionsTable() {
  const { filters, selectedSchema, permission } = useObjectTableContext();
  const queryFilters = resolveDecisionFilters(filters);

  const { data: count } = useObjectsCount({
    objectKind: selectedSchema.kind!,
    filters: queryFilters,
  });

  const { data, fetchNextPage, hasNextPage, isPending, isFetchingNextPage, error } = useObjects({
    schema: selectedSchema,
    filters: queryFilters,
    getAttributesVisible: (attributes) =>
      attributes.filter((a) => GLOBAL_PERMISSIONS_TABLE_ATTRIBUTES.includes(a.name)),
    getRelationshipsVisible: (relationships) =>
      relationships.filter((r) => GLOBAL_PERMISSIONS_TABLE_RELATIONSHIPS.includes(r.name)),
  });

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const columns = [
    ...getGlobalPermissionsTableColumns(selectedSchema),
    getObjectActionsColumn(permission),
  ];
  const rows = data?.pages.flat() ?? [];

  return (
    <InfiniteScroll scrollX hasNextPage={hasNextPage} onLoadMore={fetchNextPage}>
      <DataTable
        columns={columns}
        data={rows}
        count={count}
        isLoading={isPending || isFetchingNextPage}
        renderEmpty={() => <ObjectTableEmpty schema={selectedSchema} />}
      />
    </InfiniteScroll>
  );
}
