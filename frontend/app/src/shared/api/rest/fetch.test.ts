import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PRIORITY_HEADER } from "@/shared/api/priority";
import { MAX_RETRIES } from "@/shared/api/rate-limit/policy";
import { SHED_USER_MESSAGE } from "@/shared/api/rate-limit/shed-envelope";

import { shedResponse } from "../../../../tests/fake/shed-response";
import { FetchError, fetchUrl } from "./fetch";

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
    return fetchSpy.mock.calls[0]?.[1]?.headers as Record<string, string>;
  }

  it("stamps X-Priority: high on an Infrahub-API request with no priority arg", async () => {
    await fetchUrl("http://localhost:8000/api/search/docs?query=x");

    expect(fetchSpy).toHaveBeenCalledOnce();
    expect(initHeaders()[PRIORITY_HEADER]).toBe("high");
  });

  it("does NOT stamp X-Priority on a request to an external host", async () => {
    await fetchUrl("https://example.com/whatever");

    expect(fetchSpy).toHaveBeenCalledOnce();
    expect(initHeaders()[PRIORITY_HEADER]).toBeUndefined();
  });
});

describe("fetchUrl — a shed request", () => {
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
    // No Retry-After on these responses, so with the jitter pinned to zero
    // the replays wait a zero-length backoff.
    vi.spyOn(Math, "random").mockReturnValue(0);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("rejects with the user-facing wording once the retries are spent", async () => {
    // GIVEN
    const url = "http://localhost:8000/api/search/docs?query=x";

    // WHEN
    const outcome = await fetchUrl(url).catch((error: unknown) => error);

    // THEN
    expect(fetchSpy).toHaveBeenCalledTimes(MAX_RETRIES + 1);
    expect(outcome).toBeInstanceOf(FetchError);
    expect((outcome as FetchError).status).toBe(429);
    expect((outcome as FetchError).errors?.[0]?.message).toBe(SHED_USER_MESSAGE);
  });
});
