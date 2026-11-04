import { afterEach, describe, expect, it } from "vitest";

import { getIpPoolResourceUrl } from "@/entities/resource-manager/ui/routing/ip-pool-urls";

const initialUrl = window.location.href;

const openUrl = (search: string) =>
  window.history.replaceState({}, "", `/resource-manager/pool${search}`);

const searchOf = (url: string) => new URLSearchParams(url.split("?")[1] ?? "");

describe("IP pool URLs", () => {
  afterEach(() => {
    window.history.replaceState({}, "", initialUrl);
  });

  it("links a resource prefix and keeps the branch and the IPAM namespace", () => {
    // GIVEN
    openUrl("?branch=b1&namespace=ns-id&kind=IpamIPPrefix&pagination=nope");

    // WHEN
    const url = getIpPoolResourceUrl("pool", "resource");

    // THEN
    expect(url.split("?")[0]).toBe("/resource-manager/pool/resources/resource");
    expect(Object.fromEntries(searchOf(url))).toEqual({
      branch: "b1",
      namespace: "ns-id",
      kind: "IpamIPPrefix",
    });
  });

  it("links the pool itself without a resource prefix", () => {
    // WHEN
    const url = getIpPoolResourceUrl("pool");

    // THEN
    expect(url).toBe("/resource-manager/pool");
  });
});
