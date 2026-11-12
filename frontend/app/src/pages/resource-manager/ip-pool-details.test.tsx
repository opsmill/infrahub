import { Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup } from "vitest-browser-react";

import { store } from "@/shared/stores";

import type { IpPoolUtilization } from "@/entities/resource-manager/domain/model/ip-pool";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/domain/model/pool";
import type { IpPoolAllocationsCardProps } from "@/entities/resource-manager/ui/ip-pool/details/ip-pool-allocations-card";
import { useGetIpPool } from "@/entities/resource-manager/ui/queries/get-ip-pool.query";
import { useGetIpPoolUtilization } from "@/entities/resource-manager/ui/queries/get-ip-pool-utilization.query";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../tests/components/render";
import { generateIpPoolUtilization, generateIpPrefixPoolData } from "../../../tests/fake/ip-pool";
import { generatePermission } from "../../../tests/fake/permission";
import { generateNodeSchema } from "../../../tests/fake/schema";
import { IpPoolDetailsPage } from "./ip-pool-details";

vi.mock("@/entities/resource-manager/ui/queries/get-ip-pool.query", () => ({
  useGetIpPool: vi.fn(),
}));

vi.mock("@/entities/resource-manager/ui/queries/get-ip-pool-utilization.query", () => ({
  useGetIpPoolUtilization: vi.fn(),
}));

vi.mock("@/entities/resource-manager/ui/ip-pool/details/ip-pool-allocations-card", () => ({
  IpPoolAllocationsCard: ({ selectedResourceId }: IpPoolAllocationsCardProps) => (
    <p>Allocations of {selectedResourceId}</p>
  ),
}));

const initialNodeSchemas = store.get(nodeSchemasAtom);
const initialPath = window.location.pathname;

const pool = generateIpPrefixPoolData();
const utilization = generateIpPoolUtilization();
const [firstResource, secondResource] = utilization.resources;
const prefixPoolSchema = generateNodeSchema({
  kind: "CoreIPPrefixPool",
  name: "IPPrefixPool",
  namespace: "Core",
  inherit_from: [RESOURCE_GENERIC_KIND],
});

const mockPool = () =>
  vi.mocked(useGetIpPool).mockReturnValue({
    data: pool,
    error: null,
    isPending: false,
  } as unknown as ReturnType<typeof useGetIpPool>);

const mockUtilization = (data: IpPoolUtilization | undefined, error: Error | null = null) =>
  vi.mocked(useGetIpPoolUtilization).mockReturnValue({
    data,
    error,
    isPending: !data && !error,
  } as unknown as ReturnType<typeof useGetIpPoolUtilization>);

const renderPage = (path = `/resource-manager/${pool.id}`) => {
  window.history.replaceState(null, "", path);
  const page = (
    <IpPoolDetailsPage
      poolId={pool.id}
      schema={prefixPoolSchema}
      permission={generatePermission()}
    />
  );

  return render(
    <Routes>
      <Route path="/resource-manager/:resourcePoolId" element={page} />
      <Route path="/resource-manager/:resourcePoolId/resources/:resourceId" element={page} />
    </Routes>
  );
};

describe("IpPoolDetailsPage", () => {
  beforeEach(() => {
    store.set(nodeSchemasAtom, [prefixPoolSchema]);
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
    vi.mocked(useGetIpPool).mockReturnValue({
      data: undefined,
      error: null,
      isPending: true,
    } as unknown as ReturnType<typeof useGetIpPool>);

    // WHEN
    const component = await renderPage();

    // THEN
    await expect.element(component.getByRole("status", { name: "Loading IP pool" })).toBeVisible();
  });

  it("requests the usage while the pool is still loading", async () => {
    // GIVEN
    vi.mocked(useGetIpPool).mockReturnValue({
      data: undefined,
      error: null,
      isPending: true,
    } as unknown as ReturnType<typeof useGetIpPool>);
    mockUtilization(undefined);

    // WHEN
    await renderPage();

    // THEN
    expect(useGetIpPoolUtilization).toHaveBeenCalledWith(pool.id);
  });

  it("shows the error when the pool fails to load", async () => {
    // GIVEN
    vi.mocked(useGetIpPool).mockReturnValue({
      data: undefined,
      error: new Error("IP pool not found"),
      isPending: false,
    } as unknown as ReturnType<typeof useGetIpPool>);

    // WHEN
    const component = await renderPage();

    // THEN
    await expect.element(component.getByText("IP pool not found")).toBeVisible();
  });

  it("selects the first resource prefix when the address names none", async () => {
    // GIVEN
    mockPool();
    mockUtilization(utilization);

    // WHEN
    const component = await renderPage();

    // THEN
    await expect
      .element(component.getByRole("heading", { level: 1, name: "PAR1 fabric links" }))
      .toBeVisible();
    await expect
      .element(component.getByRole("option", { name: /^10\.10\.0\.0\/22/ }))
      .toHaveAttribute("aria-selected", "true");
    await expect.element(component.getByText(`Allocations of ${firstResource?.id}`)).toBeVisible();
  });

  it("selects the resource prefix named in the address", async () => {
    // GIVEN
    mockPool();
    mockUtilization(utilization);

    // WHEN
    const component = await renderPage(
      `/resource-manager/${pool.id}/resources/${secondResource?.id}`
    );

    // THEN
    await expect
      .element(component.getByRole("option", { name: /^10\.10\.4\.0\/22/ }))
      .toHaveAttribute("aria-selected", "true");
    await expect.element(component.getByText(`Allocations of ${secondResource?.id}`)).toBeVisible();
  });

  it("says the pool has no resource prefix", async () => {
    // GIVEN
    mockPool();
    mockUtilization(generateIpPoolUtilization({ resources: [] }));

    // WHEN
    const component = await renderPage();

    // THEN
    await expect.element(component.getByText("No resource prefixes")).toBeVisible();
  });

  it("keeps the header and shows the error when the usage fails to load", async () => {
    // GIVEN
    mockPool();
    mockUtilization(undefined, new Error("Utilization unavailable"));

    // WHEN
    const component = await renderPage();

    // THEN
    await expect
      .element(component.getByRole("heading", { level: 1, name: "PAR1 fabric links" }))
      .toBeVisible();
    await expect.element(component.getByText("Utilization unavailable")).toBeVisible();
  });

  it("keeps the loaded resource prefixes when a refresh of the usage fails", async () => {
    // GIVEN
    mockPool();
    mockUtilization(utilization, new Error("Utilization unavailable"));

    // WHEN
    const component = await renderPage();

    // THEN
    await expect
      .element(component.getByRole("option", { name: /^10\.10\.0\.0\/22/ }))
      .toBeVisible();
    await expect.element(component.getByText("Utilization unavailable")).not.toBeInTheDocument();
  });
});
