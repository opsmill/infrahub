import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PRIORITY_HEADER } from "@/shared/api/priority";

import { authMiddleware, queryClient } from "./client";

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

  it("preserves X-Priority: low when the caller pre-set it (openapi-fetch params.header opt-in)", async () => {
    // The REST `low` opt-in idiom is `params: { header: { 'X-Priority': 'low' } }`,
    // which openapi-fetch materializes on the outgoing Request's headers before
    // the middleware runs. `onRequest` must normalize-and-preserve that value,
    // not clobber it back to the `high` default.
    const request = new Request("http://localhost:8000/api/test", {
      headers: { [PRIORITY_HEADER]: "low" },
    });

    await authMiddleware.onRequest?.({ request } as never);

    expect(request.headers.get(PRIORITY_HEADER)).toBe("low");
  });
});

describe("authMiddleware 401 replay — X-Priority survives the stored clone", () => {
  let fetchQuerySpy: ReturnType<typeof vi.spyOn>;
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    // getAccessToken() must return a token so `onRequest` takes the branch that
    // captures the retry clone (no clone is stored when there is no token).
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => (key === "access_token" ? "old-token" : null),
      setItem: () => {},
      removeItem: () => {},
      clear: () => {},
    });
    // Capture the Request handed to the replay `fetch(clonedRequest)`.
    fetchSpy = vi.fn(async () => new Response(null, { status: 200 }));
    vi.stubGlobal("fetch", fetchSpy);
    fetchQuerySpy = vi.spyOn(queryClient, "fetchQuery");
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("replays the 401'd request with the original X-Priority carried on the clone", async () => {
    // GIVEN a refresh that returns a fresh token
    fetchQuerySpy.mockResolvedValue({ access_token: "new-token", refresh_token: "new-refresh" });
    const request = new Request("http://localhost:8000/api/test");

    // WHEN onRequest runs, it stamps X-Priority BEFORE cloning, so the stored
    // clone (what the replay re-sends) inherits it.
    await authMiddleware.onRequest?.({ request } as never);
    expect(request.headers.get(PRIORITY_HEADER)).toBe("high");

    // AND a 401 response triggers the stored-clone replay via fetch(clonedRequest)
    const response = new Response(null, { status: 401 });
    await authMiddleware.onResponse?.({ request, response } as never);

    // THEN the replayed request still carries X-Priority, alongside the
    // refreshed Bearer token.
    expect(fetchSpy).toHaveBeenCalledOnce();
    const replayed = fetchSpy.mock.calls[0]?.[0] as Request;
    expect(replayed.headers.get(PRIORITY_HEADER)).toBe("high");
    expect(replayed.headers.get("Authorization")).toBe("Bearer new-token");
  });
});
