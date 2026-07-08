import { type OnUrlUpdateFunction, withNuqsTestingAdapter } from "nuqs/adapters/testing";
import { describe, expect, it, vi } from "vitest";
import { renderHook } from "vitest-browser-react";

import { useSort } from "@/entities/nodes/sort/ui/hooks/use-sort";

import { generateAttributeSchema, generateNodeSchema } from "../../../../../../tests/fake/schema";

const schema = generateNodeSchema({
  attributes: [
    generateAttributeSchema({ name: "name", label: "Name", kind: "Text" }),
    generateAttributeSchema({ name: "priority", label: "Priority", kind: "Number" }),
  ],
  relationships: [],
});

describe("useSort", () => {
  it("reads sorts from the `sort` query param", async () => {
    // GIVEN
    const wrapper = withNuqsTestingAdapter({
      searchParams: "?sort=name__value__asc,priority__value__desc",
    });

    // WHEN
    const { result } = await renderHook(() => useSort(schema), { wrapper });

    // THEN
    expect(result.current.sort).toEqual([
      { field: "name__value", direction: "ASC" },
      { field: "priority__value", direction: "DESC" },
    ]);
  });

  it("keeps only the sorts that are valid for the schema", async () => {
    // GIVEN
    const wrapper = withNuqsTestingAdapter({
      searchParams: "?sort=owner__value__asc,name__value__desc",
    });

    // WHEN
    const { result } = await renderHook(() => useSort(schema), { wrapper });

    // THEN
    expect(result.current.sort).toEqual([{ field: "name__value", direction: "DESC" }]);
  });

  it("returns null when the query param is absent or carries no valid sort", async () => {
    // GIVEN
    const withoutSort = withNuqsTestingAdapter({ searchParams: "" });
    const withHostileSort = withNuqsTestingAdapter({
      searchParams: "?sort=name__value: ASC}) {password__desc",
    });

    // WHEN
    const absent = await renderHook(() => useSort(schema), { wrapper: withoutSort });
    const hostile = await renderHook(() => useSort(schema), { wrapper: withHostileSort });

    // THEN
    expect(absent.result.current.sort).toBeNull();
    expect(hostile.result.current.sort).toBeNull();
  });

  it("setSort writes the serialized sorts to the URL with history push", async () => {
    // GIVEN
    const onUrlUpdate = vi.fn<OnUrlUpdateFunction>();
    const wrapper = withNuqsTestingAdapter({ searchParams: "", onUrlUpdate });
    const hook = await renderHook(() => useSort(schema), { wrapper });

    // WHEN
    await hook.act(() => {
      hook.result.current.setSort([
        { field: "priority__value", direction: "DESC" },
        { field: "name__value", direction: "ASC" },
      ]);
    });

    // THEN
    const event = onUrlUpdate.mock.lastCall?.[0];
    expect(event?.searchParams.get("sort")).toBe("priority__value__desc,name__value__asc");
    expect(event?.options.history).toBe("push");
  });

  it("setSort with an empty list removes the query param", async () => {
    // GIVEN
    const onUrlUpdate = vi.fn<OnUrlUpdateFunction>();
    const wrapper = withNuqsTestingAdapter({
      searchParams: "?sort=name__value__desc",
      onUrlUpdate,
    });
    const hook = await renderHook(() => useSort(schema), { wrapper });

    // WHEN
    await hook.act(() => {
      hook.result.current.setSort([]);
    });

    // THEN
    const event = onUrlUpdate.mock.lastCall?.[0];
    expect(event?.searchParams.get("sort")).toBeNull();
  });
});
