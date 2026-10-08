import { afterEach, describe, expect, it, vi } from "vitest";

import { useGetNumberPool } from "@/entities/resource-manager/ui/queries/get-number-pool.query";

import { render } from "../../../tests/components/render";
import { generateNumberPoolData } from "../../../tests/fake/number-pool";
import { generatePermission } from "../../../tests/fake/permission";
import { generateNodeSchema } from "../../../tests/fake/schema";
import { NumberPoolDetailsPage } from "./number-pool-details";

vi.mock("@/entities/resource-manager/ui/queries/get-number-pool.query", () => ({
  useGetNumberPool: vi.fn(),
}));

vi.mock("@/pages/resource-manager/resource-pool-details-body", () => ({
  ResourcePoolDetailsBody: () => <p>Pool body</p>,
}));

const pool = generateNumberPoolData();

const renderPage = () =>
  render(
    <NumberPoolDetailsPage
      poolId={pool.id}
      schema={generateNodeSchema({ kind: "CoreNumberPool" })}
      permission={generatePermission()}
    />
  );

describe("NumberPoolDetailsPage", () => {
  afterEach(() => {
    vi.resetAllMocks();
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
    await expect.element(component.getByRole("heading")).not.toBeInTheDocument();
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

  it("shows the header and the body once the pool is loaded", async () => {
    // GIVEN
    vi.mocked(useGetNumberPool).mockReturnValue({
      data: pool,
      error: null,
      isPending: false,
    } as unknown as ReturnType<typeof useGetNumberPool>);

    // WHEN
    const component = await renderPage();

    // THEN
    await expect
      .element(component.getByRole("heading", { level: 1, name: "Interface speeds" }))
      .toBeVisible();
    await expect.element(component.getByText("Pool body")).toBeVisible();
  });
});
