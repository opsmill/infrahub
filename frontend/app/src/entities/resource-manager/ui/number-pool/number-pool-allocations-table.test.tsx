import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { userEvent } from "vitest/browser";

import { store } from "@/shared/stores";

import { useGetBranches } from "@/entities/branches/ui/queries/get-branches.query";
import type { NumberPoolAllocation } from "@/entities/resource-manager/domain/model/number-pool";
import { useGetNumberPoolAllocationCount } from "@/entities/resource-manager/ui/queries/get-number-pool-allocation-count.query";
import { useGetNumberPoolAllocations } from "@/entities/resource-manager/ui/queries/get-number-pool-allocations.query";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../tests/components/render";
import {
  generateNumberPoolAllocation,
  generateNumberPoolUtilization,
} from "../../../../../tests/fake/number-pool";
import { generateAttributeSchema, generateNodeSchema } from "../../../../../tests/fake/schema";
import {
  NumberPoolAllocationsTable,
  type NumberPoolAllocationsTableProps,
} from "./number-pool-allocations-table";

vi.mock("@/entities/resource-manager/ui/queries/get-number-pool-allocations.query", () => ({
  useGetNumberPoolAllocations: vi.fn(),
}));

vi.mock("@/entities/resource-manager/ui/queries/get-number-pool-allocation-count.query", () => ({
  useGetNumberPoolAllocationCount: vi.fn(),
}));

vi.mock("@/entities/branches/ui/queries/get-branches.query", () => ({
  useGetBranches: vi.fn(),
}));

const { ranges } = generateNumberPoolUtilization();
const [firstRange] = ranges;
const initialNodeSchemas = store.get(nodeSchemasAtom);

const mockAllocations = ({
  allocations,
  count = allocations.length,
  hasNextPage = false,
  fetchNextPage = vi.fn(),
}: {
  allocations: NumberPoolAllocation[];
  count?: number;
  hasNextPage?: boolean;
  fetchNextPage?: () => void;
}) => {
  vi.mocked(useGetNumberPoolAllocations).mockReturnValue({
    data: { pages: [allocations], pageParams: [0] },
    error: null,
    isPending: false,
    hasNextPage,
    isFetchingNextPage: false,
    fetchNextPage,
  } as unknown as ReturnType<typeof useGetNumberPoolAllocations>);
  vi.mocked(useGetNumberPoolAllocationCount).mockReturnValue({
    data: count,
  } as unknown as ReturnType<typeof useGetNumberPoolAllocationCount>);
};

const renderTable = (props: Partial<NumberPoolAllocationsTableProps> = {}) =>
  render(
    <div className="flex h-100 flex-col">
      <NumberPoolAllocationsTable
        poolId="pool-id"
        nodeKind="InfraInterface"
        nodeAttribute="speed"
        ranges={ranges}
        selectedRange={null}
        {...props}
      />
    </div>
  );

describe("NumberPoolAllocationsTable", () => {
  beforeEach(() => {
    // react-stately ^3.49 reads process.env.VIRT_ON under NODE_ENV=test, and browser mode has no process global.
    vi.stubGlobal("process", { env: { VIRT_ON: "1" } });
    vi.mocked(useGetBranches).mockReturnValue({
      data: [
        { id: "main-id", name: "main", is_default: true },
        { id: "b1-id", name: "b1", is_default: false },
      ],
    } as unknown as ReturnType<typeof useGetBranches>);
  });

  afterEach(() => {
    vi.resetAllMocks();
    vi.unstubAllGlobals();
    store.set(nodeSchemasAtom, initialNodeSchemas);
  });

  it("shows the range of each number when every range is listed", async () => {
    // GIVEN
    mockAllocations({ allocations: [generateNumberPoolAllocation({ value: 7 })] });

    // WHEN
    const component = await renderTable();

    // THEN
    await expect
      .element(component.getByRole("row", { name: /^7/ }))
      .toHaveTextContent("7ethernet1InfraInterfacemain1 – 50Allocated");
  });

  it("hides the Range column when one range is selected", async () => {
    // GIVEN
    mockAllocations({ allocations: [generateNumberPoolAllocation({ value: 7 })] });

    // WHEN
    const component = await renderTable({ selectedRange: firstRange });

    // THEN
    await expect
      .element(component.getByRole("columnheader", { name: "Range" }))
      .not.toBeInTheDocument();
  });

  it("links a holder to its node on the branch that holds the number", async () => {
    // GIVEN
    mockAllocations({ allocations: [generateNumberPoolAllocation({ branch: "b1" })] });

    // WHEN
    const component = await renderTable();

    // THEN
    await expect
      .element(component.getByRole("link", { name: "ethernet1" }))
      .toHaveAttribute("href", expect.stringContaining("branch=b1"));
  });

  it("links a holder on the default branch without naming a branch", async () => {
    // GIVEN
    mockAllocations({ allocations: [generateNumberPoolAllocation({ branch: "main" })] });

    // WHEN
    const component = await renderTable();

    // THEN
    await expect
      .element(component.getByRole("link", { name: "ethernet1" }))
      .not.toHaveAttribute("href", expect.stringContaining("branch="));
  });

  it("names the number and object columns after the attribute and kind the pool allocates to", async () => {
    // GIVEN
    store.set(nodeSchemasAtom, [
      generateNodeSchema({
        kind: "InfraInterface",
        name: "Interface",
        namespace: "Infra",
        label: "Interface",
        attributes: [generateAttributeSchema({ name: "speed", label: "Speed" })],
      }),
    ]);
    mockAllocations({ allocations: [generateNumberPoolAllocation()] });

    // WHEN
    const component = await renderTable();

    // THEN
    await expect.element(component.getByRole("columnheader", { name: "Speed" })).toBeVisible();
    await expect.element(component.getByRole("columnheader", { name: "Interface" })).toBeVisible();
  });

  it("falls back to generic column names when the kind has no schema", async () => {
    // GIVEN
    mockAllocations({ allocations: [generateNumberPoolAllocation()] });

    // WHEN
    const component = await renderTable();

    // THEN
    await expect.element(component.getByRole("columnheader", { name: "Number" })).toBeVisible();
    await expect.element(component.getByRole("columnheader", { name: "Object" })).toBeVisible();
  });

  it("shows a number without thousands separators", async () => {
    // GIVEN
    mockAllocations({ allocations: [generateNumberPoolAllocation({ value: 4_200_000_000 })] });

    // WHEN
    const component = await renderTable();

    // THEN
    await expect
      .element(component.getByRole("rowheader", { name: "4200000000", exact: true }))
      .toBeVisible();
  });

  it("links the branch that holds a number to its branch page", async () => {
    // GIVEN
    mockAllocations({ allocations: [generateNumberPoolAllocation({ branch: "feature/b1" })] });

    // WHEN
    const component = await renderTable();

    // THEN
    await expect
      .element(component.getByRole("link", { name: "feature/b1" }))
      .toHaveAttribute("href", "/branches/feature%2Fb1");
  });

  it("shows placeholder rows while the first page loads", async () => {
    // GIVEN
    mockAllocations({ allocations: [] });
    vi.mocked(useGetNumberPoolAllocations).mockReturnValue({
      data: undefined,
      error: null,
      isPending: true,
      hasNextPage: false,
      isFetchingNextPage: false,
      fetchNextPage: vi.fn(),
    } as unknown as ReturnType<typeof useGetNumberPoolAllocations>);

    // WHEN
    const component = await renderTable();

    // THEN
    await expect
      .element(component.getByRole("status", { name: "Loading allocations" }))
      .toBeVisible();
  });

  it("marks a number a user provided", async () => {
    // GIVEN
    mockAllocations({ allocations: [generateNumberPoolAllocation({ provenance: "PROVIDED" })] });

    // WHEN
    const component = await renderTable();

    // THEN
    await expect.element(component.getByText("Provided")).toBeVisible();
  });

  it("says when the pool has no allocated number", async () => {
    // GIVEN
    mockAllocations({ allocations: [] });

    // WHEN
    const component = await renderTable();

    // THEN
    await expect.element(component.getByText("No allocations yet")).toBeVisible();
  });

  it("says when the selected range has no allocated number", async () => {
    // GIVEN
    mockAllocations({ allocations: [] });

    // WHEN
    const component = await renderTable({ selectedRange: firstRange });

    // THEN
    await expect.element(component.getByText("No allocations in 1 – 50")).toBeVisible();
  });

  it("shows the total count of allocated numbers", async () => {
    // GIVEN
    mockAllocations({ allocations: [generateNumberPoolAllocation()], count: 1250 });

    // WHEN
    const component = await renderTable();

    // THEN
    await expect.element(component.getByText("1,250")).toBeVisible();
  });

  it("loads the next rows when the user scrolls to the end", async () => {
    // GIVEN
    const fetchNextPage = vi.fn();
    mockAllocations({
      allocations: Array.from({ length: 40 }, (_, index) =>
        generateNumberPoolAllocation({ value: index + 1 })
      ),
      count: 250,
      hasNextPage: true,
      fetchNextPage,
    });
    const component = await renderTable();
    const grid = component.getByRole("grid", { name: "Allocations" }).element();

    // WHEN
    grid.scrollTop = grid.scrollHeight;
    grid.dispatchEvent(new Event("scroll"));

    // THEN
    await expect.poll(() => fetchNextPage).toHaveBeenCalled();
  });

  it("moves keyboard focus from a row to its holder link", async () => {
    // GIVEN
    mockAllocations({ allocations: [generateNumberPoolAllocation()] });
    const component = await renderTable();
    await userEvent.keyboard("{Tab}");

    // WHEN
    await userEvent.keyboard("{ArrowRight}{ArrowRight}");

    // THEN
    await expect.element(component.getByRole("link", { name: "ethernet1" })).toHaveFocus();
  });
});
