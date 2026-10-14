import { Card } from "@infrahub/ui";
import React from "react";

import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { SearchInput } from "@/shared/components/inputs/search-input";
import { Skeleton } from "@/shared/components/loading/skeleton";
import { formatNumberDisplay } from "@/shared/utils/number";

import type {
  NumberPoolData,
  NumberPoolDivision,
} from "@/entities/resource-manager/domain/model/number-pool";
import {
  NUMBER_POOL_DIVISION_SORT_BY_USAGE,
  type NumberPoolDivisionSort,
  useNumberPoolDivisionTableState,
} from "@/entities/resource-manager/ui/hooks/use-number-pool-division-table-state";
import { useNumberPoolScopeFields } from "@/entities/resource-manager/ui/hooks/use-number-pool-scope-fields";
import { NumberPoolDivisionsTable } from "@/entities/resource-manager/ui/number-pool/details/number-pool-divisions-table";
import { useGetNumberPoolDivisions } from "@/entities/resource-manager/ui/queries/get-number-pool-divisions.query";

const SKELETON_WIDTHS = ["w-40", "w-56", "w-32", "w-48", "w-64", "w-36"];

const filterDivisions = (divisions: NumberPoolDivision[], search: string) => {
  const needle = search.trim().toLowerCase();
  if (!needle) return divisions;
  return divisions.filter((division) =>
    division.entries.some((entry) => entry.label.toLowerCase().includes(needle))
  );
};

const compareLabels = (a: string, b: string) =>
  a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });

const sortDivisions = (divisions: NumberPoolDivision[], sort: NumberPoolDivisionSort) => {
  const sign = sort.direction === "ascending" ? 1 : -1;
  const labelOf = (division: NumberPoolDivision) =>
    division.entries.find((entry) => entry.path === sort.by)?.label ?? "";

  // the backend order is the default sort, so ties keep it
  return [...divisions].sort((a, b) => {
    if (sort.by === NUMBER_POOL_DIVISION_SORT_BY_USAGE) {
      return sign * (a.usage.utilization - b.usage.utilization);
    }
    return sign * compareLabels(labelOf(a), labelOf(b));
  });
};

function SkeletonRows() {
  return (
    <div role="status" aria-busy="true" aria-label="Loading allocation scopes">
      {SKELETON_WIDTHS.map((width) => (
        <Row key={width} className="h-11 justify-between border-b px-3">
          <Skeleton className={`h-3 ${width}`} />
          <Skeleton className="h-1.5 w-56" />
        </Row>
      ))}
    </div>
  );
}

interface EmptyMessageProps {
  title: string;
  description?: string;
}

function EmptyMessage({ title, description }: EmptyMessageProps) {
  return (
    <Col className="items-center gap-1 px-6 py-12 text-center text-sm">
      <p className="font-medium">{title}</p>
      {description && <p className="max-w-sm text-pretty text-foreground-muted">{description}</p>}
    </Col>
  );
}

function useShownDivisions(pool: NumberPoolData) {
  const [{ search, sort }] = useNumberPoolDivisionTableState();
  const deferredSearch = React.useDeferredValue(search);
  const query = useGetNumberPoolDivisions(pool.id);
  const divisions = query.data?.divisions ?? [];

  return {
    ...query,
    divisions,
    shown: sortDivisions(filterDivisions(divisions, deferredSearch), sort),
    isSearching: deferredSearch.trim() !== "",
  };
}

interface DivisionsCountProps {
  pool: NumberPoolData;
}

function DivisionsCount({ pool }: DivisionsCountProps) {
  const { data, divisions, shown, isSearching } = useShownDivisions(pool);

  if (!data) return null;

  return (
    <span className="text-foreground-muted text-sm tabular-nums">
      {isSearching
        ? `${formatNumberDisplay(shown.length)} of ${formatNumberDisplay(divisions.length)}`
        : formatNumberDisplay(divisions.length)}
    </span>
  );
}

interface DivisionsSearchProps {
  pool: NumberPoolData;
}

function DivisionsSearch({ pool }: DivisionsSearchProps) {
  const fields = useNumberPoolScopeFields(pool);
  const [{ search }, { setSearch }] = useNumberPoolDivisionTableState();

  return (
    <SearchInput
      className="h-7 w-64 text-sm"
      placeholder={`Search ${fields.map((field) => field.label.toLowerCase()).join(" or ")}`}
      value={search}
      onChange={setSearch}
      onPressReset={() => setSearch("")}
    />
  );
}

interface DivisionsContentProps {
  pool: NumberPoolData;
}

function DivisionsContent({ pool }: DivisionsContentProps) {
  const fields = useNumberPoolScopeFields(pool);
  const [{ sort }, { setSort }] = useNumberPoolDivisionTableState();
  const { error, isPending, divisions, shown } = useShownDivisions(pool);

  if (isPending) return <SkeletonRows />;

  if (error) return <ErrorScreen message={error.message} />;

  if (divisions.length === 0) {
    return (
      <EmptyMessage
        title="No numbers allocated yet."
        description="An allocation scope appears here once an object in it holds a number from this pool."
      />
    );
  }

  if (shown.length === 0) return <EmptyMessage title="No allocation scope matches" />;

  return (
    <NumberPoolDivisionsTable
      poolId={pool.id}
      fields={fields}
      divisions={shown}
      sort={sort}
      onSortChange={setSort}
    />
  );
}

export interface NumberPoolDivisionsListProps {
  pool: NumberPoolData;
}

export function NumberPoolDivisionsList({ pool }: NumberPoolDivisionsListProps) {
  return (
    <Card className="mx-2 mb-2 min-h-0 grow overflow-hidden">
      <Row className="flex-wrap border-b px-3 py-2">
        <h2 className="font-semibold text-sm">Allocation scopes</h2>
        <DivisionsCount pool={pool} />
        <DivisionsSearch pool={pool} />
      </Row>
      <div className="relative min-h-0 flex-1 overflow-auto overscroll-contain">
        <DivisionsContent pool={pool} />
      </div>
    </Card>
  );
}
