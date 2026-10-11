import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import type { GraphqlQueryCostEstimate } from "@/entities/nodes/object/domain/model/graphql-query-cost";

import { render } from "../../../../../../tests/components/render";
import { GraphqlQueryCostWarning } from "./graphql-query-cost-warning";

const NOW = new Date("2026-10-11T12:00:00Z");

const HIGH_COST_ESTIMATE: GraphqlQueryCostEstimate & { level: string } = {
  level: "high",
  high_cost_database_rows: 250_000,
  statistics_computed_at: "2026-10-09T12:00:00Z",
  expected: { database_rows: 99_188 },
  worst_case: { database_rows: 1_138_406 },
  fields_without_estimate: 0,
  costliest_fields: [
    {
      path: "InfraInterface/device/interfaces/device/interfaces",
      worst_case_database_rows: 1_100_000,
    },
    { path: "InfraInterface/device/interfaces", worst_case_database_rows: 35_000 },
  ],
};

describe("GraphqlQueryCostWarning", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("shows the estimated rows, the limit and the costliest fields of a high-cost query", async () => {
    // GIVEN
    const costLevel = "high";

    // WHEN
    const component = await render(
      <GraphqlQueryCostWarning costLevel={costLevel} costEstimate={HIGH_COST_ESTIMATE} />
    );

    // THEN
    await expect
      .element(component.getByRole("region", { name: "High estimated cost" }))
      .toBeVisible();
    await expect.element(component.getByText("1,138,406 database rows")).toBeVisible();
    await expect.element(component.getByText("99,188 database rows")).toBeVisible();
    await expect.element(component.getByText("250,000 database rows")).toBeVisible();
    await expect
      .element(
        component.getByRole("listitem").filter({
          hasText: "InfraInterface/device/interfaces/device/interfaces: 1,100,000 database rows",
        })
      )
      .toBeVisible();
    await expect
      .element(
        component.getByRole("listitem").filter({
          hasText: "InfraInterface/device/interfaces: 35,000 database rows",
        })
      )
      .toBeVisible();
  });

  test("shows when the statistics used by the estimate were computed", async () => {
    // GIVEN
    const costLevel = "high";

    // WHEN
    const component = await render(
      <GraphqlQueryCostWarning costLevel={costLevel} costEstimate={HIGH_COST_ESTIMATE} />
    );

    // THEN
    await expect.element(component.getByText("2 days ago")).toBeVisible();
  });

  test("links to the documentation of the cost level", async () => {
    // GIVEN
    const costLevel = "high";

    // WHEN
    const component = await render(
      <GraphqlQueryCostWarning costLevel={costLevel} costEstimate={HIGH_COST_ESTIMATE} />
    );

    // THEN
    await expect
      .element(component.getByRole("link", { name: "How the cost level is estimated" }))
      .toHaveAttribute(
        "href",
        expect.stringMatching(
          /\/docs\/development-resources\/graphql\/query-cost#view-the-cost-level-of-a-stored-query$/
        )
      );
  });

  test("states the number of fields left out of the figures", async () => {
    // GIVEN
    const costEstimate = { ...HIGH_COST_ESTIMATE, fields_without_estimate: 2 };

    // WHEN
    const component = await render(
      <GraphqlQueryCostWarning costLevel="high" costEstimate={costEstimate} />
    );

    // THEN
    await expect
      .element(
        component.getByText(
          "2 fields of the query have no estimate and are not counted in these figures."
        )
      )
      .toBeVisible();
  });

  test("shows the warning without figures when the estimate cannot be read", async () => {
    // GIVEN
    const costEstimate = { level: "high" };

    // WHEN
    const component = await render(
      <GraphqlQueryCostWarning costLevel="high" costEstimate={costEstimate} />
    );

    // THEN
    await expect
      .element(component.getByRole("region", { name: "High estimated cost" }))
      .toBeVisible();
    expect(component.getByText("Worst case").query()).toBeNull();
  });

  test("shows nothing for a low-cost query", async () => {
    // GIVEN
    const costEstimate = { ...HIGH_COST_ESTIMATE, level: "low" };

    // WHEN
    const component = await render(
      <GraphqlQueryCostWarning costLevel="low" costEstimate={costEstimate} />
    );

    // THEN
    expect(component.getByRole("region", { name: "High estimated cost" }).query()).toBeNull();
    expect(component.getByText("database rows").query()).toBeNull();
  });
});
