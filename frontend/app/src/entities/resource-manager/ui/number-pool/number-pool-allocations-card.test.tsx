import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { store } from "@/shared/stores";

import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/domain/model/pool";
import type { NumberPoolAllocationsTableProps } from "@/entities/resource-manager/ui/number-pool/number-pool-allocations-table";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../tests/components/render";
import { generateNumberPoolUtilization } from "../../../../../tests/fake/number-pool";
import { generateNodeSchema } from "../../../../../tests/fake/schema";
import {
  NumberPoolAllocationsCard,
  type NumberPoolAllocationsCardProps,
} from "./number-pool-allocations-card";

vi.mock("@/entities/resource-manager/ui/number-pool/number-pool-allocations-table", () => ({
  NumberPoolAllocationsTable: ({ selectedRange }: NumberPoolAllocationsTableProps) => (
    <p>Numbers of {selectedRange ? selectedRange.id : "every range"}</p>
  ),
}));

const initialNodeSchemas = store.get(nodeSchemasAtom);

const { ranges } = generateNumberPoolUtilization();
const [firstRange] = ranges;

const renderCard = (props: Partial<NumberPoolAllocationsCardProps> = {}) =>
  render(
    <NumberPoolAllocationsCard
      poolId="pool-id"
      nodeKind="InfraInterface"
      nodeAttribute="speed"
      ranges={ranges}
      selectedRangeId={null}
      {...props}
    />
  );

describe("NumberPoolAllocationsCard", () => {
  beforeEach(() => {
    store.set(nodeSchemasAtom, [
      generateNodeSchema({
        kind: "CoreNumberPool",
        name: "NumberPool",
        namespace: "Core",
        inherit_from: [RESOURCE_GENERIC_KIND],
      }),
    ]);
  });

  afterEach(() => {
    store.set(nodeSchemasAtom, initialNodeSchemas);
  });

  it("lists the numbers of every range when no range is selected", async () => {
    // WHEN
    const component = await renderCard();

    // THEN
    await expect.element(component.getByText("Numbers of every range")).toBeVisible();
  });

  it("lists the numbers of the selected range", async () => {
    // WHEN
    const component = await renderCard({ selectedRangeId: firstRange?.id });

    // THEN
    await expect.element(component.getByText(`Numbers of ${firstRange?.id}`)).toBeVisible();
  });

  it("explains that a selected range is not part of the pool", async () => {
    // WHEN
    const component = await renderCard({ selectedRangeId: "not-in-pool" });

    // THEN
    await expect.element(component.getByText("Range not found")).toBeVisible();
    await expect
      .element(component.getByRole("link", { name: "View all ranges" }))
      .toHaveAttribute("href", "/resource-manager/pool-id");
    await expect.element(component.getByText(/^Numbers of/)).not.toBeInTheDocument();
  });

  it("shows nothing when the pool has no range", async () => {
    // WHEN
    const component = await renderCard({ ranges: [] });

    // THEN
    expect(component.container.textContent).toBe("");
  });
});
