import { afterEach, describe, expect, it } from "vitest";

import {
  getNumberPoolDivisionsUrl,
  getNumberPoolDivisionUrl,
  getNumberPoolRangeUrl,
} from "@/entities/resource-manager/ui/routing/number-pool-urls";

const initialUrl = window.location.href;

const openUrl = (search: string) =>
  window.history.replaceState({}, "", `/resource-manager/pool${search}`);

const searchOf = (url: string) => new URLSearchParams(url.split("?")[1] ?? "");

const scopeParam = `allocation_scope=${encodeURIComponent(JSON.stringify(["device-id"]))}`;

describe("number pool URLs", () => {
  afterEach(() => {
    window.history.replaceState({}, "", initialUrl);
  });

  it("keeps the allocation scope, the branch and the allocation filters on range links", () => {
    // GIVEN
    openUrl(`?${scopeParam}&branch=b1&allocation_source=ALLOCATED&allocation_scope_search=atl`);

    // WHEN
    const url = getNumberPoolRangeUrl("pool", "range");

    // THEN
    expect(url.split("?")[0]).toBe("/resource-manager/pool/ranges/range");
    expect(Object.fromEntries(searchOf(url))).toEqual({
      allocation_scope: JSON.stringify(["device-id"]),
      branch: "b1",
      allocation_source: "ALLOCATED",
    });
  });

  it("links an allocation scope without the range, the search or the sort", () => {
    // GIVEN
    openUrl("?branch=b1&allocation_scope_search=atl&allocation_scope_sort=device:asc");

    // WHEN
    const url = getNumberPoolDivisionUrl("pool", ["device-id", 100]);

    // THEN
    expect(url.split("?")[0]).toBe("/resource-manager/pool");
    expect(Object.fromEntries(searchOf(url))).toEqual({
      branch: "b1",
      allocation_scope: JSON.stringify(["device-id", 100]),
    });
  });

  it("links back to every allocation scope without the open one", () => {
    // GIVEN
    openUrl(`?${scopeParam}&branch=b1`);

    // WHEN
    const url = getNumberPoolDivisionsUrl("pool");

    // THEN
    expect(url).toBe("/resource-manager/pool?branch=b1");
  });
});
