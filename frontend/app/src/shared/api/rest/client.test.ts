import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PRIORITY_HEADER } from "@/shared/api/priority";
import { MAX_RETRIES } from "@/shared/api/rate-limit/policy";
import { SHED_USER_MESSAGE } from "@/shared/api/rate-limit/shed-envelope";

import { shedResponse } from "../../../../tests/fake/shed-response";
import { apiClient, authMiddleware, queryClient } from "./client";

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

  it("stamps X-Priority: high by default", async () => {
    const request = new Request("http://localhost:8000/api/test");

    await authMiddleware.onRequest?.({ request } as never);

    expect(request.headers.get(PRIORITY_HEADER)).toBe("high");
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
    // GIVEN
    fetchQuerySpy.mockResolvedValue({ access_token: "new-token", refresh_token: "new-refresh" });
    const request = new Request("http://localhost:8000/api/test");

    // WHEN
    await authMiddleware.onRequest?.({ request } as never);
    const response = new Response(null, { status: 401 });
    await authMiddleware.onResponse?.({ request, response } as never);

    // THEN
    expect(fetchSpy).toHaveBeenCalledOnce();
    const replayed = fetchSpy.mock.calls[0]?.[0] as Request;
    expect(replayed.headers.get(PRIORITY_HEADER)).toBe("high");
    expect(replayed.headers.get("Authorization")).toBe("Bearer new-token");
  });
});

describe("apiClient — a shed request", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.stubGlobal("localStorage", {
      getItem: () => null,
      setItem: () => {},
      removeItem: () => {},
      clear: () => {},
    });
    fetchSpy = vi.fn(async () => shedResponse());
    vi.stubGlobal("fetch", fetchSpy);
    vi.spyOn(Math, "random").mockReturnValue(0);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("hands the caller the user-facing wording once the retries are spent", async () => {
    // GIVEN a server that sheds every attempt

    // WHEN
    const { error, response } = await apiClient.GET("/api/config");

    // THEN
    expect(fetchSpy).toHaveBeenCalledTimes(MAX_RETRIES + 1);
    expect(response.status).toBe(429);
    expect(error).toMatchObject({ errors: [{ message: SHED_USER_MESSAGE }] });
  });
});
