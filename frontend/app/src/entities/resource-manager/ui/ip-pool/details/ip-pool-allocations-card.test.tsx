import { describe, expect, it, vi } from "vitest";

import { IP_PREFIX_POOL } from "@/entities/resource-manager/domain/model/pool";
import type { IpPoolAllocationsTableProps } from "@/entities/resource-manager/ui/ip-pool/details/ip-pool-allocations-table";

import { render } from "../../../../../../tests/components/render";
import { generateIpPoolUtilization } from "../../../../../../tests/fake/ip-pool";
import { IpPoolAllocationsCard, type IpPoolAllocationsCardProps } from "./ip-pool-allocations-card";

vi.mock("@/entities/resource-manager/ui/ip-pool/details/ip-pool-allocations-table", () => ({
  IpPoolAllocationsTable: ({ resource }: IpPoolAllocationsTableProps) => (
    <p>Prefixes of {resource.id}</p>
  ),
}));

const { resources } = generateIpPoolUtilization();
const [firstResource] = resources;

const renderCard = (props: Partial<IpPoolAllocationsCardProps> = {}) =>
  render(
    <IpPoolAllocationsCard
      poolId="pool-id"
      poolKind={IP_PREFIX_POOL}
      resources={resources}
      selectedResourceId={firstResource?.id ?? null}
      {...props}
    />
  );

describe("IpPoolAllocationsCard", () => {
  it("lists the prefixes of the selected resource prefix", async () => {
    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText(`Prefixes of ${firstResource?.id}`)).toBeVisible();
  });

  it("explains that the selected resource prefix is not part of the pool", async () => {
    // WHEN
    const component = await renderCard({ selectedResourceId: "not-in-pool" });

    // THEN
    await expect.element(component.getByText("Resource prefix not found")).toBeVisible();
    await expect
      .element(component.getByRole("link", { name: "View the pool" }))
      .toHaveAttribute("href", "/resource-manager/pool-id");
    await expect.element(component.getByText(/^Prefixes of/)).not.toBeInTheDocument();
  });

  it("shows nothing when the pool has no resource prefix", async () => {
    // WHEN
    const component = await renderCard({ resources: [] });

    // THEN
    expect(component.container.textContent).toBe("");
  });
});
