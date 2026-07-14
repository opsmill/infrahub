import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PRIORITY_HEADER } from "@/shared/api/priority";

import { authMiddleware } from "./client";

describe("authMiddleware.onRequest — outbound X-Priority header", () => {
  beforeEach(() => {
    // The middleware calls getAccessToken(), which reads localStorage. In
    // node mode there is no localStorage, so provide a minimal stub returning
    // no token (the auth branch is irrelevant to the priority assertion).
    vi.stubGlobal("localStorage", {
      getItem: () => null,
      setItem: () => {},
      removeItem: () => {},
      clear: () => {},
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("stamps X-Priority: high when no priority option is provided", async () => {
    const request = new Request("http://localhost:8000/api/test");

    // `onRequest` sets the priority header before the 401-replay clone is
    // captured, so this is exactly what the outbound request carries.
    await authMiddleware.onRequest?.({ request } as never);

    expect(request.headers.get(PRIORITY_HEADER)).toBe("high");
  });
});
