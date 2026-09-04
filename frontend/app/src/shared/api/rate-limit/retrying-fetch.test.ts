import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { retryingFetch } from "./retrying-fetch";

const TEST_URL = "http://localhost:8000/api/test";

const SHED_BODY = JSON.stringify({
  data: null,
  errors: [{ message: "Server is shedding load; retry later.", extensions: { code: 429 } }],
});

// No Retry-After, so a replay waits out a jittered backoff of at most 300ms.
// Real timers throughout: deciding a mutation's fate means reading the response
// body, which never settles while the clock is faked.
function shed(): Response {
  return new Response(SHED_BODY, {
    status: 429,
    headers: { "Content-Type": "application/json" },
  });
}

function foreignShed(): Response {
  return new Response(JSON.stringify({ detail: "slow down" }), {
    status: 429,
    headers: { "Content-Type": "application/json" },
  });
}

describe("retryingFetch", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends a successful request once", async () => {
    fetchSpy.mockResolvedValue(new Response(null, { status: 200 }));

    const response = await retryingFetch(new Request(TEST_URL));

    expect(fetchSpy).toHaveBeenCalledOnce();
    expect(response.status).toBe(200);
  });

  it("replays a shed GET and returns the response that succeeds", async () => {
    fetchSpy
      .mockResolvedValueOnce(shed())
      .mockResolvedValueOnce(new Response(null, { status: 200 }));

    const response = await retryingFetch(new Request(TEST_URL));

    expect(response.status).toBe(200);
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  it("sends a fresh clone per attempt and leaves the caller's request intact", async () => {
    fetchSpy
      .mockResolvedValueOnce(shed())
      .mockResolvedValueOnce(new Response(null, { status: 200 }));
    const request = new Request(TEST_URL, { method: "POST", body: '{"query":"{ ok }"}' });

    await retryingFetch(request);

    const first = fetchSpy.mock.calls[0]?.[0] as Request;
    const second = fetchSpy.mock.calls[1]?.[0] as Request;
    expect(first).not.toBe(request);
    expect(second).not.toBe(first);
    expect(request.bodyUsed).toBe(false);
    await expect(second.text()).resolves.toBe('{"query":"{ ok }"}');
  });

  it("replays a shed mutation, which the server answered before running it", async () => {
    fetchSpy
      .mockResolvedValueOnce(shed())
      .mockResolvedValueOnce(new Response(null, { status: 200 }));

    const response = await retryingFetch(new Request(TEST_URL, { method: "POST", body: "{}" }));

    expect(response.status).toBe(200);
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  it("does not replay a mutation rejected by something other than Infrahub", async () => {
    fetchSpy.mockResolvedValue(foreignShed());

    const response = await retryingFetch(new Request(TEST_URL, { method: "POST", body: "{}" }));

    expect(response.status).toBe(429);
    expect(fetchSpy).toHaveBeenCalledOnce();
  });

  it("replays a request passed as a url and init pair", async () => {
    fetchSpy
      .mockResolvedValueOnce(shed())
      .mockResolvedValueOnce(new Response(null, { status: 200 }));

    const response = await retryingFetch(TEST_URL, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    expect(response.status).toBe(200);
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(fetchSpy.mock.calls[1]?.[0]).toBe(TEST_URL);
  });

  it("stops replaying when the caller aborts", async () => {
    const controller = new AbortController();
    fetchSpy.mockImplementation(async () => {
      controller.abort();
      return shed();
    });

    const response = await retryingFetch(new Request(TEST_URL, { signal: controller.signal }));

    expect(response.status).toBe(429);
    expect(fetchSpy).toHaveBeenCalledOnce();
  });
});
