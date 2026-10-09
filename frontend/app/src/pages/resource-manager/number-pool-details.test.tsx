import { Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { store } from "@/shared/stores";

import type { NumberPoolUtilization } from "@/entities/resource-manager/domain/model/number-pool";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/domain/model/pool";
import type { NumberPoolAllocationsCardProps } from "@/entities/resource-manager/ui/number-pool/number-pool-allocations-card";
import { useGetNumberPool } from "@/entities/resource-manager/ui/queries/get-number-pool.query";
import { useGetNumberPoolUtilization } from "@/entities/resource-manager/ui/queries/get-number-pool-utilization.query";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../tests/components/render";
import {
  generateNumberPoolData,
  generateNumberPoolUtilization,
} from "../../../tests/fake/number-pool";
import { generatePermission } from "../../../tests/fake/permission";
import { generateNodeSchema } from "../../../tests/fake/schema";
import { NumberPoolDetailsPage } from "./number-pool-details";

vi.mock("@/entities/resource-manager/ui/queries/get-number-pool.query", () => ({
  useGetNumberPool: vi.fn(),
}));

vi.mock("@/entities/resource-manager/ui/queries/get-number-pool-utilization.query", () => ({
  useGetNumberPoolUtilization: vi.fn(),
}));

vi.mock("@/entities/resource-manager/ui/number-pool/number-pool-allocations-card", () => ({
  NumberPoolAllocationsCard: ({ selectedRangeId }: NumberPoolAllocationsCardProps) => (
    <p>Numbers of {selectedRangeId ?? "every range"}</p>
  ),
}));

const initialNodeSchemas = store.get(nodeSchemasAtom);
const initialPath = window.location.pathname;

const pool = generateNumberPoolData();
const utilization = generateNumberPoolUtilization();
const [firstRange] = utilization.ranges;
const numberPoolSchema = generateNodeSchema({
  kind: "CoreNumberPool",
  name: "NumberPool",
  namespace: "Core",
  inherit_from: [RESOURCE_GENERIC_KIND],
});

const mockPool = () =>
  vi.mocked(useGetNumberPool).mockReturnValue({
    data: pool,
    error: null,
    isPending: false,
  } as unknown as ReturnType<typeof useGetNumberPool>);

const mockUtilization = (data: NumberPoolUtilization | undefined, error: Error | null = null) =>
  vi.mocked(useGetNumberPoolUtilization).mockReturnValue({
    data,
    error,
    isPending: !data && !error,
  } as unknown as ReturnType<typeof useGetNumberPoolUtilization>);

const renderPage = (path = `/resource-manager/${pool.id}`) => {
  window.history.replaceState(null, "", path);
  const page = (
    <NumberPoolDetailsPage
      poolId={pool.id}
      schema={numberPoolSchema}
      permission={generatePermission()}
    />
  );

  return render(
    <Routes>
      <Route path="/resource-manager/:resourcePoolId" element={page} />
      <Route path="/resource-manager/:resourcePoolId/ranges/:rangeId" element={page} />
    </Routes>
  );
};

describe("NumberPoolDetailsPage", () => {
  beforeEach(() => {
    store.set(nodeSchemasAtom, [numberPoolSchema]);
  });

  afterEach(() => {
    vi.resetAllMocks();
    store.set(nodeSchemasAtom, initialNodeSchemas);
    window.history.replaceState(null, "", initialPath);
  });

  it("shows the header placeholder while the pool loads", async () => {
    // GIVEN
    vi.mocked(useGetNumberPool).mockReturnValue({
      data: undefined,
      error: null,
      isPending: true,
    } as unknown as ReturnType<typeof useGetNumberPool>);

    // WHEN
    const component = await renderPage();

    // THEN
    await expect
      .element(component.getByRole("status", { name: "Loading number pool" }))
      .toBeVisible();
    await expect.element(component.getByRole("heading", { level: 1 })).not.toBeInTheDocument();
  });

  it("shows the error when the pool fails to load", async () => {
    // GIVEN
    vi.mocked(useGetNumberPool).mockReturnValue({
      data: undefined,
      error: new Error("Number pool not found"),
      isPending: false,
    } as unknown as ReturnType<typeof useGetNumberPool>);

    // WHEN
    const component = await renderPage();

    // THEN
    await expect.element(component.getByText("Number pool not found")).toBeVisible();
  });

  it("lists the numbers of every range on the pool's own address", async () => {
    // GIVEN
    mockPool();
    mockUtilization(utilization);

    // WHEN
    const component = await renderPage();

    // THEN
    await expect
      .element(component.getByRole("heading", { level: 1, name: "Interface speeds" }))
      .toBeVisible();
    await expect.element(component.getByText("Numbers of every range")).toBeVisible();
  });

  it("selects the range named in the address and lists its numbers", async () => {
    // GIVEN
    mockPool();
    mockUtilization(utilization);

    // WHEN
    const component = await renderPage(`/resource-manager/${pool.id}/ranges/${firstRange?.id}`);

    // THEN
    await expect
      .element(component.getByRole("option", { name: /^1 – 50/ }))
      .toHaveAttribute("aria-selected", "true");
    await expect.element(component.getByText(`Numbers of ${firstRange?.id}`)).toBeVisible();
  });

  it("says the pool has no range", async () => {
    // GIVEN
    mockPool();
    mockUtilization(generateNumberPoolUtilization({ ranges: [] }));

    // WHEN
    const component = await renderPage();

    // THEN
    await expect.element(component.getByText("No ranges")).toBeVisible();
  });

  it("shows the error when the ranges fail to load", async () => {
    // GIVEN
    mockPool();
    mockUtilization(undefined, new Error("The pool has an allocation scope"));

    // WHEN
    const component = await renderPage();

    // THEN
    await expect.element(component.getByText("The pool has an allocation scope")).toBeVisible();
  });
});
