import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup } from "vitest-browser-react";

import { store } from "@/shared/stores";

import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/domain/model/pool";
import { useGetIpPoolUtilization } from "@/entities/resource-manager/ui/queries/get-ip-pool-utilization.query";
import { genericSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../tests/components/render";
import { generateIpPoolUtilization } from "../../../../../tests/fake/ip-pool";
import { generateGenericSchema } from "../../../../../tests/fake/schema";
import { BreadcrumbResourceManager } from "./breadcrumb-resource-manager";

vi.mock("@/entities/resource-manager/ui/queries/get-ip-pool-utilization.query", () => ({
  useGetIpPoolUtilization: vi.fn(),
}));

vi.mock("@/entities/navigation/ui/breadcrumbs/breadcrumb-object-details", () => ({
  BreadcrumbObjectDetails: () => null,
}));

const initialGenericSchemas = store.get(genericSchemasAtom);
const initialPath = window.location.pathname;

const utilization = generateIpPoolUtilization();
const [, secondResource] = utilization.resources;

const renderBreadcrumb = (path: string) => {
  window.history.replaceState(null, "", path);

  return render(
    <Routes>
      <Route
        path="/resource-manager/:resourcePoolId/resources/:resourceId"
        element={<BreadcrumbResourceManager />}
      />
    </Routes>
  );
};

describe("BreadcrumbResourceManager", () => {
  afterEach(async () => {
    await cleanup();
    window.history.replaceState(null, "", initialPath);
    vi.resetAllMocks();
    store.set(genericSchemasAtom, initialGenericSchemas);
  });

  it("links the resource prefix named in the address", async () => {
    // GIVEN
    store.set(genericSchemasAtom, [generateGenericSchema({ kind: RESOURCE_GENERIC_KIND })]);
    vi.mocked(useGetIpPoolUtilization).mockReturnValue({
      data: utilization,
      error: null,
      isPending: false,
    } as unknown as ReturnType<typeof useGetIpPoolUtilization>);

    // WHEN
    const component = await renderBreadcrumb(
      `/resource-manager/pool-id/resources/${secondResource?.id}`
    );

    // THEN
    await expect
      .element(component.getByRole("link", { name: secondResource?.display_label }))
      .toHaveAttribute("href", `/resource-manager/pool-id/resources/${secondResource?.id}`);
    expect(useGetIpPoolUtilization).toHaveBeenCalledWith("pool-id");
  });

  it("keeps the resource prefix link when a refresh fails", async () => {
    // GIVEN
    store.set(genericSchemasAtom, [generateGenericSchema({ kind: RESOURCE_GENERIC_KIND })]);
    vi.mocked(useGetIpPoolUtilization).mockReturnValue({
      data: utilization,
      error: new Error("refresh failed"),
      isPending: false,
    } as unknown as ReturnType<typeof useGetIpPoolUtilization>);

    // WHEN
    const component = await renderBreadcrumb(
      `/resource-manager/pool-id/resources/${secondResource?.id}`
    );

    // THEN
    await expect
      .element(component.getByRole("link", { name: secondResource?.display_label }))
      .toBeVisible();
  });
});
