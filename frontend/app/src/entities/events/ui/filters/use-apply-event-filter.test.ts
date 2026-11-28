import { type OnUrlUpdateFunction, withNuqsTestingAdapter } from "nuqs/adapters/testing";
import { describe, expect, it, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { QSP } from "@/shared/config/qsp";

import type { Filter } from "@/entities/nodes/filters/domain/model/filter";

import { useApplyEventFilter } from "./use-apply-event-filter";

const branchFilter: Filter = { name: "branches__value", value: "main" };

async function applyEventFilter(name: string, initialFilters: Filter[], value: Filter["value"]) {
  const onUrlUpdate = vi.fn<OnUrlUpdateFunction>();
  const searchParams = initialFilters.length
    ? `?${QSP.FILTER}=${encodeURIComponent(JSON.stringify(initialFilters))}`
    : "";
  const wrapper = withNuqsTestingAdapter({ searchParams, onUrlUpdate });
  const hook = await renderHook(() => useApplyEventFilter(name), { wrapper });

  await hook.act(() => {
    hook.result.current(value);
  });

  const raw = onUrlUpdate.mock.lastCall?.[0].searchParams.get(QSP.FILTER);
  return raw ? (JSON.parse(raw) as Filter[]) : [];
}

describe("useApplyEventFilter", () => {
  it("adds the `<name>__value` filter after the other filters", async () => {
    // GIVEN
    const initialFilters = [branchFilter];

    // WHEN
    const filters = await applyEventFilter("hasChildren", initialFilters, true);

    // THEN
    expect(filters).toEqual([branchFilter, { name: "hasChildren__value", value: true }]);
  });

  it("replaces an existing `<name>__value` filter and keeps the other filters", async () => {
    // GIVEN
    const initialFilters = [
      { name: "eventType__value", value: "infrahub.node.created" },
      branchFilter,
    ];

    // WHEN
    const filters = await applyEventFilter("eventType", initialFilters, "infrahub.node.deleted");

    // THEN
    expect(filters).toEqual([
      branchFilter,
      { name: "eventType__value", value: "infrahub.node.deleted" },
    ]);
  });

  it.each([null, undefined])(
    "removes the `<name>__value` filter for a %s value and keeps the other filters",
    async (value) => {
      // GIVEN
      const initialFilters = [
        { name: "eventType__value", value: "infrahub.node.created" },
        branchFilter,
      ];

      // WHEN
      const filters = await applyEventFilter("eventType", initialFilters, value);

      // THEN
      expect(filters).toEqual([branchFilter]);
    }
  );
});
