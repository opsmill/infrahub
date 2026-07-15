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
    expect(result.current.customSort).toEqual([
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
    expect(result.current.customSort).toEqual([{ field: "name__value", direction: "DESC" }]);
  });

  it("keeps only the first occurrence of a field duplicated in the query param", async () => {
    // GIVEN
    const wrapper = withNuqsTestingAdapter({
      searchParams: "?sort=name__value__asc,name__value__desc",
    });

    // WHEN
    const { result } = await renderHook(() => useSort(schema), { wrapper });

    // THEN
    expect(result.current.customSort).toEqual([{ field: "name__value", direction: "ASC" }]);
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
    expect(absent.result.current.customSort).toBeNull();
    expect(hostile.result.current.customSort).toBeNull();
  });

  it("setCustomSort writes the serialized sorts to the URL with history push", async () => {
    // GIVEN
    const onUrlUpdate = vi.fn<OnUrlUpdateFunction>();
    const wrapper = withNuqsTestingAdapter({ searchParams: "", onUrlUpdate });
    const hook = await renderHook(() => useSort(schema), { wrapper });

    // WHEN
    await hook.act(() => {
      hook.result.current.setCustomSort([
        { field: "priority__value", direction: "DESC" },
        { field: "name__value", direction: "ASC" },
      ]);
    });

    // THEN
    const event = onUrlUpdate.mock.lastCall?.[0];
    expect(event?.searchParams.get("sort")).toBe("priority__value__desc,name__value__asc");
    expect(event?.options.history).toBe("push");
  });

  it("setCustomSort with an empty list removes the query param", async () => {
    // GIVEN
    const onUrlUpdate = vi.fn<OnUrlUpdateFunction>();
    const wrapper = withNuqsTestingAdapter({
      searchParams: "?sort=name__value__desc",
      onUrlUpdate,
    });
    const hook = await renderHook(() => useSort(schema), { wrapper });

    // WHEN
    await hook.act(() => {
      hook.result.current.setCustomSort([]);
    });

    // THEN
    const event = onUrlUpdate.mock.lastCall?.[0];
    expect(event?.searchParams.get("sort")).toBeNull();
  });

  it("derives defaultSort from the schema order_by tokens", async () => {
    // GIVEN
    const schemaWithDefaults = generateNodeSchema({
      ...schema,
      order_by: ["name__value", "priority__value__desc"],
    });
    const wrapper = withNuqsTestingAdapter({ searchParams: "" });

    // WHEN
    const { result } = await renderHook(() => useSort(schemaWithDefaults), { wrapper });

    // THEN
    expect(result.current.defaultSort).toEqual([
      { field: "name__value", direction: "ASC" },
      { field: "priority__value", direction: "DESC" },
    ]);
  });

  it("returns a null defaultSort when the schema defines no order_by", async () => {
    // GIVEN
    const schemaWithoutDefaults = generateNodeSchema({ ...schema, order_by: [] });
    const wrapper = withNuqsTestingAdapter({ searchParams: "" });

    // WHEN
    const { result } = await renderHook(() => useSort(schemaWithoutDefaults), { wrapper });

    // THEN
    expect(result.current.defaultSort).toBeNull();
  });

  it("applies the custom sort over the schema default", async () => {
    // GIVEN
    const wrapper = withNuqsTestingAdapter({ searchParams: "?sort=priority__value__desc" });

    // WHEN
    const { result } = await renderHook(() => useSort(schema), { wrapper });

    // THEN
    expect(result.current.appliedSort).toEqual([{ field: "priority__value", direction: "DESC" }]);
  });

  it("applies the schema default when there is no custom sort", async () => {
    // GIVEN
    const wrapper = withNuqsTestingAdapter({ searchParams: "" });

    // WHEN
    const { result } = await renderHook(() => useSort(schema), { wrapper });

    // THEN
    expect(result.current.appliedSort).toEqual([{ field: "name__value", direction: "ASC" }]);
  });

  it("applies the schema default when the custom sort has no valid field", async () => {
    // GIVEN
    const wrapper = withNuqsTestingAdapter({ searchParams: "?sort=unknown__value__desc" });

    // WHEN
    const { result } = await renderHook(() => useSort(schema), { wrapper });

    // THEN
    expect(result.current.appliedSort).toEqual([{ field: "name__value", direction: "ASC" }]);
  });

  it("applies an empty sort when there is no custom sort nor schema default", async () => {
    // GIVEN
    const schemaWithoutDefaults = generateNodeSchema({ ...schema, order_by: [] });
    const wrapper = withNuqsTestingAdapter({ searchParams: "" });

    // WHEN
    const { result } = await renderHook(() => useSort(schemaWithoutDefaults), { wrapper });

    // THEN
    expect(result.current.appliedSort).toEqual([]);
  });
});
