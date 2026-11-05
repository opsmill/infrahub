import { afterEach, describe, expect, it } from "vitest";

import { getIpamNamespaceUrl } from "@/entities/ipam/ip-namespaces/ui/routing/ipam-urls";

const initialUrl = window.location.href;

describe("getIpamNamespaceUrl", () => {
  afterEach(() => {
    window.history.replaceState({}, "", initialUrl);
  });

  it("names a namespace that is not the default one", () => {
    // GIVEN
    window.history.replaceState({}, "", "/resource-manager/pool?branch=b1");

    // WHEN
    const url = getIpamNamespaceUrl({ id: "ns-id", isDefault: false });

    // THEN
    expect(url).toBe("/ipam?branch=b1&namespace=ns-id");
  });

  it("leaves the parameter out for the default namespace", () => {
    // GIVEN
    window.history.replaceState({}, "", "/resource-manager/pool?namespace=other");

    // WHEN
    const url = getIpamNamespaceUrl({ id: "ns-id", isDefault: true });

    // THEN
    expect(url).toBe("/ipam");
  });
});
