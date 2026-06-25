import { type OnUrlUpdateFunction, withNuqsTestingAdapter } from "nuqs/adapters/testing";
import { beforeEach, describe, expect, test, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import type { ModelSchema } from "@/entities/schema/types";

import { useSort } from "./use-sort";

vi.mock("@/entities/nodes/object/domain/sortable-field", () => ({
  getSortableFields: () => [
    { field: "name__value", label: "Name" },
    { field: "owner__name__value", label: "Owner › Name" },
    { field: "node_metadata__updated_at", label: "Updated at" },
  ],
}));

const schema = { kind: "TestNode", order_by: ["name__value"] } as ModelSchema;

function render(searchParams: string, onUrlUpdate?: OnUrlUpdateFunction) {
  return renderHook(() => useSort(schema), {
    wrapper: withNuqsTestingAdapter({ searchParams, onUrlUpdate }),
  });
}

describe("useSort", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("returns null and leaves the URL clean when there is no sort param", async () => {
    // GIVEN
    const onUrlUpdate = vi.fn();
    // WHEN
    const { result } = await render("", onUrlUpdate);
    // THEN
    expect(result.current[0]).toBeNull();
    expect(onUrlUpdate).not.toHaveBeenCalled();
  });

  test("reads a valid sort param, excluding unknown fields without rewriting the URL", async () => {
    // GIVEN
    const onUrlUpdate = vi.fn();
    // WHEN
    const { result } = await render("?sort=owner__name__value__desc,gone__value__asc", onUrlUpdate);
    // THEN
    expect(result.current[0]).toEqual([{ field: "owner__name__value", direction: "DESC" }]);
    expect(onUrlUpdate).not.toHaveBeenCalled();
  });

  test("writes the full array to the sort param", async () => {
    // GIVEN
    const onUrlUpdate = vi.fn();
    const hook = await render("", onUrlUpdate);
    // WHEN
    await hook.act(() => {
      hook.result.current[1]([
        { field: "name__value", direction: "ASC" },
        { field: "owner__name__value", direction: "DESC" },
      ]);
    });
    // THEN
    expect(onUrlUpdate.mock.lastCall?.[0].searchParams.get("sort")).toBe(
      "name__value__asc,owner__name__value__desc"
    );
  });

  test("normalizes a sort equal to the schema default to null, removing the param", async () => {
    // GIVEN
    const onUrlUpdate = vi.fn();
    const hook = await render("?sort=owner__name__value__desc", onUrlUpdate);
    // WHEN
    await hook.act(() => {
      hook.result.current[1]([{ field: "name__value", direction: "ASC" }]);
    });
    // THEN — the param is dropped so we fall back onto the live default
    expect(onUrlUpdate.mock.lastCall?.[0].searchParams.get("sort")).toBeNull();
    expect(hook.result.current[0]).toBeNull();
  });

  test("removes the sort param when cleared", async () => {
    // GIVEN
    const onUrlUpdate = vi.fn();
    const hook = await render("?sort=name__value__desc", onUrlUpdate);
    // WHEN
    await hook.act(() => {
      hook.result.current[1]([]);
    });
    // THEN
    expect(onUrlUpdate.mock.lastCall?.[0].searchParams.get("sort")).toBeNull();
    expect(hook.result.current[0]).toBeNull();
  });
});
