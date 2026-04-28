import ErrorScreen from "@/shared/components/errors/error-screen";
import { DataTable } from "@/shared/components/table/data-table";
import { InfiniteScroll } from "@/shared/components/utils/infinite-scroll";
import type { Filter } from "@/shared/hooks/useFilters";

import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectTableEmpty } from "@/entities/nodes/object/ui/object-table/object-table-empty";
import { getObjectActionsColumn } from "@/entities/nodes/object/ui/object-table/utils/get-object-actions-column";
import { useObjects } from "@/entities/nodes/object/ui/queries/get-objects.query";
import { useObjectsCount } from "@/entities/nodes/object/ui/queries/get-objects-count.query";
import { objectDecisionOptions } from "@/entities/role-manager/constants";
import {
  getObjectPermissionTableColumns,
  OBJECT_PERMISSION_TABLE_ATTRIBUTES,
  OBJECT_PERMISSION_TABLE_RELATIONSHIPS,
} from "@/entities/role-manager/ui/get-object-permission-table-columns";

export function resolveObjectPermissionFilters(filters: Filter[]): Filter[] {
  return filters.map((filter) => {
    if (filter.name === "decision__value") {
      const numericValue = objectDecisionOptions.find((o) => o.label === filter.value)?.value;
      return { ...filter, value: numericValue ?? filter.value };
    }
    return filter;
  });
}

export function ObjectPermissionTable() {
  const { filters: rawFilters, selectedSchema, permission } = useObjectTableContext();
  const filters = resolveObjectPermissionFilters(rawFilters);

  const { data: count } = useObjectsCount({
    objectKind: selectedSchema.kind!,
    filters,
  });

  const { data, fetchNextPage, hasNextPage, isPending, isFetchingNextPage, error } = useObjects({
    schema: selectedSchema,
    filters,
    getAttributesVisible: (attributes) =>
      attributes.filter((a) => OBJECT_PERMISSION_TABLE_ATTRIBUTES.includes(a.name)),
    getRelationshipsVisible: (relationships) =>
      relationships.filter((r) => OBJECT_PERMISSION_TABLE_RELATIONSHIPS.includes(r.name)),
  });

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const columns = [
    ...getObjectPermissionTableColumns(selectedSchema),
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
