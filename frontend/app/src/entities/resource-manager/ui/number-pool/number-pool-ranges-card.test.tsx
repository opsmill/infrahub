import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { userEvent } from "vitest/browser";

import { ReactAriaRouterProvider } from "@/app/providers/react-aria-router-provider";

import { store } from "@/shared/stores";

import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/domain/model/pool";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { render } from "../../../../../tests/components/render";
import { generateNumberPoolUtilization } from "../../../../../tests/fake/number-pool";
import { generateNodeSchema } from "../../../../../tests/fake/schema";
import { NumberPoolRangesCard, type NumberPoolRangesCardProps } from "./number-pool-ranges-card";

const initialNodeSchemas = store.get(nodeSchemasAtom);
const initialPath = window.location.pathname;

const utilization = generateNumberPoolUtilization();
const [firstRange, secondRange] = utilization.ranges;

const renderCard = (props: Partial<NumberPoolRangesCardProps> = {}) =>
  render(
    <ReactAriaRouterProvider>
      <NumberPoolRangesCard
        poolId="pool-id"
        poolType="User"
        utilization={utilization}
        selectedRangeId={null}
        {...props}
      />
    </ReactAriaRouterProvider>
  );

describe("NumberPoolRangesCard", () => {
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
    window.history.replaceState(null, "", initialPath);
  });

  it("lists All ranges first, then the ranges in the given order", async () => {
    // WHEN
    const component = await renderCard();

    // THEN
    const options = component.getByRole("option").elements();
    expect(options.map((option) => option.textContent)).toEqual([
      expect.stringContaining("All ranges"),
      expect.stringContaining("1 – 50Weight 10"),
      expect.stringContaining("51 – 100Weight 0"),
    ]);
  });

  it("selects All ranges when no range is selected", async () => {
    // WHEN
    const component = await renderCard();

    // THEN
    await expect
      .element(component.getByRole("option", { name: /^All ranges/ }))
      .toHaveAttribute("aria-selected", "true");
  });

  it("selects the range named in the address", async () => {
    // WHEN
    const component = await renderCard({ selectedRangeId: secondRange?.id });

    // THEN
    await expect
      .element(component.getByRole("option", { name: /^51 – 100/ }))
      .toHaveAttribute("aria-selected", "true");
  });

  it("selects nothing for a range that is not in the pool", async () => {
    // WHEN
    const component = await renderCard({ selectedRangeId: "not-in-pool" });

    // THEN
    const selected = component
      .getByRole("option")
      .elements()
      .filter((option) => option.getAttribute("aria-selected") === "true");
    expect(selected).toHaveLength(0);
  });

  it("asks to edit a user-created pool that has no range", async () => {
    // WHEN
    const component = await renderCard({
      utilization: generateNumberPoolUtilization({ ranges: [] }),
    });

    // THEN
    await expect.element(component.getByText("No ranges")).toBeVisible();
    await expect.element(component.getByText(/Edit the pool to add one\./)).toBeVisible();
  });

  it("points to the schema for a schema-defined pool that has no range", async () => {
    // WHEN
    const component = await renderCard({
      poolType: "Schema",
      utilization: generateNumberPoolUtilization({ ranges: [] }),
    });

    // THEN
    await expect.element(component.getByText(/Add one in the schema\./)).toBeVisible();
  });

  it("opens the next range with the arrow and Enter keys", async () => {
    // GIVEN
    await renderCard();
    await userEvent.keyboard("{Tab}");

    // WHEN
    await userEvent.keyboard("{ArrowDown}{Enter}");

    // THEN
    await expect
      .poll(() => window.location.pathname)
      .toBe(`/resource-manager/pool-id/ranges/${firstRange?.id}`);
  });
});
