import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PRIORITY_HEADER } from "@/shared/api/priority";

import { fetchUrl } from "./fetch";

describe("fetchUrl — outbound X-Priority header", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.stubGlobal("localStorage", {
      getItem: () => null,
      setItem: () => {},
      removeItem: () => {},
      clear: () => {},
    });

    fetchSpy = vi.fn(
      async () =>
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
    );
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function initHeaders(): Record<string, string> {
    // fetchUrl builds a plain-object `headers` and calls fetch(url, init).
    return fetchSpy.mock.calls[0]?.[1]?.headers as Record<string, string>;
  }

  it("stamps X-Priority: high on an Infrahub-API request with no priority arg", async () => {
    await fetchUrl("http://localhost:8000/api/search/docs?query=x");

    expect(fetchSpy).toHaveBeenCalledOnce();
    expect(initHeaders()[PRIORITY_HEADER]).toBe("high");
  });

  it("does NOT stamp X-Priority on a request to an external host (FR-007)", async () => {
    await fetchUrl("https://example.com/whatever");

    expect(fetchSpy).toHaveBeenCalledOnce();
    expect(initHeaders()[PRIORITY_HEADER]).toBeUndefined();
  });
});
