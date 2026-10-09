import type { GraphQLResult } from "@/shared/api/graphql/types";
import { waitFor } from "@/shared/utils/common";

import type {
  GetNumberPoolAllocationCountFromApiParams,
  NumberPoolAllocationCountResponse,
} from "@/entities/resource-manager/api/get-number-pool-allocation-count-from-api";
import type {
  GetNumberPoolAllocationsFromApiParams,
  NumberPoolAllocationsResponse,
} from "@/entities/resource-manager/api/get-number-pool-allocations-from-api";
import type { NumberPoolUtilizationResponse } from "@/entities/resource-manager/api/get-number-pool-utilization-from-api";

// The number pool queries answer from fixed data on the backend until they read the database, and that data matches no real pool.
export const USE_FAKE_NUMBER_POOL_DATA = true;

const FAKE_LATENCY_MS = 300;
const DEFAULT_BRANCH = "main";
const OTHER_BRANCH = "fabric-pod-3";
const SITES = ["par1", "ams2", "fra1", "lon3", "nyc1", "sjc2"];
const ROLES = ["leaf", "spine", "border-leaf"];

interface FakeRange {
  id: string;
  start: number;
  end: number;
  weight: number;
  allocated: number;
}

// Range 2 holds no number, so its empty state shows; ranges 1 and 3 span several pages.
const FAKE_RANGES: FakeRange[] = [
  { id: "fake-range-1", start: 64_512, end: 64_999, weight: 10, allocated: 412 },
  { id: "fake-range-2", start: 65_000, end: 65_534, weight: 0, allocated: 0 },
  { id: "fake-range-3", start: 4_200_000_000, end: 4_200_000_999, weight: 5, allocated: 150 },
];

interface FakeRow {
  value: number;
  branch: string;
  provenance: "ALLOCATED" | "PROVIDED";
  holderId: string;
  holderLabel: string;
  rangeId: string;
}

const buildRows = (): FakeRow[] => {
  let index = 0;

  return FAKE_RANGES.flatMap((range) =>
    Array.from({ length: range.allocated }, (_, offset) => {
      index += 1;
      const site = SITES[index % SITES.length];
      const role = ROLES[index % ROLES.length];

      return {
        value: range.start + offset,
        branch: index % 13 === 0 ? OTHER_BRANCH : DEFAULT_BRANCH,
        provenance: index % 17 === 0 ? "PROVIDED" : "ALLOCATED",
        holderId: `fake-device-${index}`,
        holderLabel: `${role}-${site}-${String(index).padStart(3, "0")}`,
        rangeId: range.id,
      };
    })
  );
};

const FAKE_ROWS = buildRows();

const figuresOf = (rows: FakeRow[], size: number) => {
  const used = rows.length;
  const usedBranches = rows.filter(({ branch }) => branch !== DEFAULT_BRANCH).length;
  const usedDefaultBranch = used - usedBranches;
  const percent = (part: number) => (size === 0 ? 0 : (part / size) * 100);

  return {
    size,
    used,
    used_default_branch: usedDefaultBranch,
    used_branches: usedBranches,
    utilization: percent(used),
  };
};

const sizeOf = ({ start, end }: FakeRange) => end - start + 1;

export async function getFakeNumberPoolUtilization(): Promise<
  GraphQLResult<NumberPoolUtilizationResponse>
> {
  await waitFor(FAKE_LATENCY_MS);

  const poolSize = FAKE_RANGES.reduce((total, range) => total + sizeOf(range), 0);

  return {
    data: {
      InfrahubNumberPoolUtilization: {
        figures: figuresOf(FAKE_ROWS, poolSize),
        ranges: FAKE_RANGES.map((range) => ({
          id: range.id,
          start: range.start,
          end: range.end,
          weight: range.weight,
          figures: figuresOf(
            FAKE_ROWS.filter(({ rangeId }) => rangeId === range.id),
            sizeOf(range)
          ),
        })),
      },
    },
  };
}

const refuseUnknownRange = (poolId: string, rangeId: string | undefined) =>
  rangeId && !FAKE_RANGES.some(({ id }) => id === rangeId)
    ? [{ message: `The pool ${poolId} has no range ${rangeId}` }]
    : undefined;

const rowsOf = (rangeId: string | undefined) =>
  rangeId ? FAKE_ROWS.filter((row) => row.rangeId === rangeId) : FAKE_ROWS;

export async function getFakeNumberPoolAllocations({
  poolId,
  rangeId,
  offset,
  limit,
}: GetNumberPoolAllocationsFromApiParams): Promise<GraphQLResult<NumberPoolAllocationsResponse>> {
  await waitFor(FAKE_LATENCY_MS);

  const errors = refuseUnknownRange(poolId, rangeId);
  if (errors) return { data: { InfrahubNumberPoolAllocations: { allocations: [] } }, errors };

  return {
    data: {
      InfrahubNumberPoolAllocations: {
        allocations: rowsOf(rangeId)
          .slice(offset, offset + limit)
          .map((row) => ({
            value: row.value,
            branch: row.branch,
            provenance: row.provenance,
            holder: { id: row.holderId, kind: "InfraDevice", display_label: row.holderLabel },
            range: { id: row.rangeId },
          })),
      },
    },
  };
}

export async function getFakeNumberPoolAllocationCount({
  poolId,
  rangeId,
}: GetNumberPoolAllocationCountFromApiParams): Promise<
  GraphQLResult<NumberPoolAllocationCountResponse>
> {
  await waitFor(FAKE_LATENCY_MS);

  const errors = refuseUnknownRange(poolId, rangeId);
  if (errors) return { data: { InfrahubNumberPoolAllocations: { count: 0 } }, errors };

  return { data: { InfrahubNumberPoolAllocations: { count: rowsOf(rangeId).length } } };
}
