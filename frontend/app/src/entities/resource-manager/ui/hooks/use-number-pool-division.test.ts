import { withNuqsTestingAdapter } from "nuqs/adapters/testing";
import { describe, expect, it } from "vitest";
import { renderHook } from "vitest-browser-react";

import { useNumberPoolDivision } from "@/entities/resource-manager/ui/hooks/use-number-pool-division";

const renderWithUrl = (searchParams: string, fields: string[]) =>
  renderHook(() => useNumberPoolDivision(fields), {
    wrapper: withNuqsTestingAdapter({ searchParams }),
  });

const withValue = (values: unknown) =>
  `?allocation_scope=${encodeURIComponent(JSON.stringify(values))}`;

describe("useNumberPoolDivision", () => {
  it("reports no allocation scope when the URL names none", async () => {
    // GIVEN
    const searchParams = "";

    // WHEN
    const { result } = await renderWithUrl(searchParams, ["device"]);

    // THEN
    expect(result.current).toEqual({ status: "none" });
  });

  it("pairs each value with its field and keeps the value types", async () => {
    // GIVEN
    const searchParams = withValue(["device-id", 100, "100", true, ""]);

    // WHEN
    const { result } = await renderWithUrl(searchParams, [
      "device",
      "speed",
      "unit",
      "enabled",
      "role",
    ]);

    // THEN
    expect(result.current).toEqual({
      status: "selected",
      selector: [
        { path: "device", value: "device-id" },
        { path: "speed", value: 100 },
        { path: "unit", value: "100" },
        { path: "enabled", value: true },
        { path: "role", value: "" },
      ],
    });
  });

  it("reports an unreadable link when the value is not JSON", async () => {
    // GIVEN
    const searchParams = "?allocation_scope=nonsense";

    // WHEN
    const { result } = await renderWithUrl(searchParams, ["device"]);

    // THEN
    expect(result.current).toEqual({ status: "invalid", cause: { reason: "unreadable" } });
  });

  it("reports an unreadable link when an item is not a string, a number or a boolean", async () => {
    // GIVEN
    const searchParams = withValue([{ id: "device-id" }]);

    // WHEN
    const { result } = await renderWithUrl(searchParams, ["device"]);

    // THEN
    expect(result.current).toEqual({ status: "invalid", cause: { reason: "unreadable" } });
  });

  it("reports how many values the link gives when that differs from the number of fields", async () => {
    // GIVEN
    const searchParams = withValue(["device-id"]);

    // WHEN
    const { result } = await renderWithUrl(searchParams, ["device", "role"]);

    // THEN
    expect(result.current).toEqual({
      status: "invalid",
      cause: { reason: "count", count: 1 },
    });
  });
});
