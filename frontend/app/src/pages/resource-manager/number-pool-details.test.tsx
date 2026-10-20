import { Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup } from "vitest-browser-react";

import { store } from "@/shared/stores";

import type { NumberPoolUtilization } from "@/entities/resource-manager/domain/model/number-pool";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/domain/model/pool";
import type { NumberPoolAllocationsCardProps } from "@/entities/resource-manager/ui/number-pool/details/number-pool-allocations-card";
import type { NumberPoolDivisionsListProps } from "@/entities/resource-manager/ui/number-pool/details/number-pool-divisions-list";
import { useGetNumberPool } from "@/entities/resource-manager/ui/queries/get-number-pool.query";
import { useGetNumberPoolDivisions } from "@/entities/resource-manager/ui/queries/get-number-pool-divisions.query";
import { useGetNumberPoolUtilization } from "@/entities/resource-manager/ui/queries/get-number-pool-utilization.query";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../tests/components/render";
import {
  generateNumberPoolData,
  generateNumberPoolDivisions,
  generateNumberPoolUtilization,
} from "../../../tests/fake/number-pool";
import { generatePermission } from "../../../tests/fake/permission";
import { generateNodeSchema, generateRelationshipSchema } from "../../../tests/fake/schema";
import { NumberPoolDetailsPage } from "./number-pool-details";

vi.mock("@/entities/resource-manager/ui/queries/get-number-pool.query", () => ({
  useGetNumberPool: vi.fn(),
}));

vi.mock("@/entities/resource-manager/ui/queries/get-number-pool-utilization.query", () => ({
  useGetNumberPoolUtilization: vi.fn(),
}));

vi.mock("@/entities/resource-manager/ui/queries/get-number-pool-divisions.query", () => ({
  useGetNumberPoolDivisions: vi.fn(),
}));

vi.mock("@/entities/resource-manager/ui/number-pool/details/number-pool-allocations-card", () => ({
  NumberPoolAllocationsCard: ({ selectedRangeId, division }: NumberPoolAllocationsCardProps) => (
    <p>
      Numbers of {selectedRangeId ?? "every range"}
      {division && ` in ${division.map(({ value }) => value).join(" / ")}`}
    </p>
  ),
}));

vi.mock("@/entities/resource-manager/ui/number-pool/details/number-pool-divisions-list", () => ({
  NumberPoolDivisionsList: ({ pool }: NumberPoolDivisionsListProps) => (
    <p>Allocation scopes of {pool.name.value}</p>
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

const scopedPool = generateNumberPoolData({ allocation_scope: { value: ["device"] } });
const divisions = generateNumberPoolDivisions({ fields: ["device"], count: 2 });
const [firstDivision] = divisions.divisions;
const interfaceSchema = generateNodeSchema({
  kind: "InfraInterface",
  name: "Interface",
  namespace: "Infra",
  relationships: [generateRelationshipSchema({ name: "device", label: "Device" })],
});

const scopeParam = (values: unknown) =>
  `allocation_scope=${encodeURIComponent(JSON.stringify(values))}`;

const mockDivisions = () =>
  vi.mocked(useGetNumberPoolDivisions).mockReturnValue({
    data: divisions,
    error: null,
    isPending: false,
  } as unknown as ReturnType<typeof useGetNumberPoolDivisions>);

const mockPool = (data = pool) =>
  vi.mocked(useGetNumberPool).mockReturnValue({
    data,
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
    store.set(nodeSchemasAtom, [numberPoolSchema, interfaceSchema]);
  });

  afterEach(async () => {
    // the page re-renders when the address changes, so it must be gone before the mocks are reset
    await cleanup();
    window.history.replaceState(null, "", initialPath);
    vi.resetAllMocks();
    store.set(nodeSchemasAtom, initialNodeSchemas);
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

  it("lists the allocation scopes of a scoped pool without reading its pool-wide usage", async () => {
    // GIVEN
    mockPool(scopedPool);
    mockUtilization(utilization);

    // WHEN
    const component = await renderPage();

    // THEN
    await expect
      .element(component.getByText("Allocation scopes of Interface speeds"))
      .toBeVisible();
    expect(useGetNumberPoolUtilization).not.toHaveBeenCalled();
  });

  it("says when the allocation scope in the address cannot be read", async () => {
    // GIVEN
    mockPool(scopedPool);
    mockUtilization(utilization);

    // WHEN
    const component = await renderPage(`/resource-manager/${pool.id}?allocation_scope=nonsense`);

    // THEN
    await expect
      .element(component.getByRole("heading", { name: "Cannot open this allocation scope" }))
      .toBeVisible();
    await expect
      .element(
        component.getByText(
          "The allocation scope in this link cannot be read. The link may be incomplete or edited by hand."
        )
      )
      .toBeVisible();
    await expect
      .element(component.getByRole("link", { name: "View all allocation scopes" }))
      .toBeVisible();
  });

  it("says how many values the address gives when the pool's allocation scope has another number of fields", async () => {
    // GIVEN
    mockPool(scopedPool);
    mockUtilization(utilization);
    const values = encodeURIComponent(JSON.stringify(["device-id", "extra"]));

    // WHEN
    const component = await renderPage(`/resource-manager/${pool.id}?allocation_scope=${values}`);

    // THEN
    await expect
      .element(
        component.getByText(
          "This link gives 2 values, but this pool divides its numbers by 1 field: Device. The link may have been edited, or copied from another pool."
        )
      )
      .toBeVisible();
  });

  it("shows the allocation scope named in the address with its ranges and numbers", async () => {
    // GIVEN
    mockPool(scopedPool);
    mockUtilization(utilization);
    mockDivisions();
    const values = firstDivision?.entries.map(({ value }) => value);

    // WHEN
    const component = await renderPage(`/resource-manager/${pool.id}?${scopeParam(values)}`);

    // THEN
    await expect
      .element(component.getByRole("button", { name: /Allocation scope/ }))
      .toHaveTextContent(firstDivision?.label ?? "");
    await expect
      .element(component.getByText(`Numbers of every range in ${values?.join(" / ")}`))
      .toBeVisible();
    expect(useGetNumberPoolUtilization).toHaveBeenCalledWith({
      poolId: pool.id,
      division: [{ path: "device", value: values?.[0] }],
    });
  });

  it("keeps the range named in the address selected inside an allocation scope", async () => {
    // GIVEN
    mockPool(scopedPool);
    mockUtilization(utilization);
    mockDivisions();
    const values = firstDivision?.entries.map(({ value }) => value);

    // WHEN
    const component = await renderPage(
      `/resource-manager/${pool.id}/ranges/${firstRange?.id}?${scopeParam(values)}`
    );

    // THEN
    await expect
      .element(component.getByRole("option", { name: /^1 – 50/ }))
      .toHaveAttribute("aria-selected", "true");
    await expect
      .element(component.getByText(`Numbers of ${firstRange?.id} in ${values?.join(" / ")}`))
      .toBeVisible();
  });
});
