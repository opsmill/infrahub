import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  foreignRateLimitResponse,
  jsonResponse,
  SHED_BODY,
  shedResponse,
} from "../../../../tests/fake/shed-response";
import { retryingFetch } from "./retrying-fetch";

const TEST_URL = "http://localhost:8000/api/test";

const ok = () => new Response(null, { status: 200 });

describe("retryingFetch", () => {
  let fetchSpy: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    // These responses advise no wait, so with the jitter pinned to zero a
    // replay waits a zero-length backoff instead of a real one.
    vi.spyOn(Math, "random").mockReturnValue(0);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("sends a successful request once", async () => {
    // GIVEN
    fetchSpy.mockResolvedValue(ok());

    // WHEN
    const response = await retryingFetch(new Request(TEST_URL));

    // THEN
    expect(fetchSpy).toHaveBeenCalledOnce();
    expect(response.status).toBe(200);
  });

  it("replays a shed GET and returns the response that succeeds", async () => {
    // GIVEN
    fetchSpy.mockResolvedValueOnce(shedResponse()).mockResolvedValueOnce(ok());

    // WHEN
    const response = await retryingFetch(new Request(TEST_URL));

    // THEN
    expect(response.status).toBe(200);
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  it("sends a fresh clone per attempt and leaves the caller's request intact", async () => {
    // GIVEN
    fetchSpy.mockResolvedValueOnce(shedResponse()).mockResolvedValueOnce(ok());
    const request = new Request(TEST_URL, { method: "POST", body: '{"query":"{ ok }"}' });

    // WHEN
    await retryingFetch(request);

    // THEN
    const first = fetchSpy.mock.calls[0]?.[0] as Request;
    const second = fetchSpy.mock.calls[1]?.[0] as Request;
    expect(first).not.toBe(request);
    expect(second).not.toBe(first);
    expect(request.bodyUsed).toBe(false);
    await expect(second.text()).resolves.toBe('{"query":"{ ok }"}');
  });

  it("replays a shed mutation, which the server answered before running it", async () => {
    // GIVEN
    fetchSpy.mockResolvedValueOnce(shedResponse()).mockResolvedValueOnce(ok());
    const mutation = new Request(TEST_URL, { method: "POST", body: "{}" });

    // WHEN
    const response = await retryingFetch(mutation);

    // THEN
    expect(response.status).toBe(200);
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  it("does not replay a mutation rejected by something other than Infrahub", async () => {
    // GIVEN
    fetchSpy.mockResolvedValue(foreignRateLimitResponse());
    const mutation = new Request(TEST_URL, { method: "POST", body: "{}" });

    // WHEN
    const response = await retryingFetch(mutation);

    // THEN
    expect(response.status).toBe(429);
    expect(fetchSpy).toHaveBeenCalledOnce();
  });

  it("does not replay a mutation whose 429 has the shed envelope but not the marker", async () => {
    // GIVEN a body that looks like a shed but that a handler could have written
    fetchSpy.mockResolvedValue(jsonResponse(SHED_BODY, 429));
    const mutation = new Request(TEST_URL, { method: "POST", body: "{}" });

    // WHEN
    const response = await retryingFetch(mutation);

    // THEN
    expect(response.status).toBe(429);
    expect(fetchSpy).toHaveBeenCalledOnce();
  });

  it("replays a request passed as a url and init pair", async () => {
    // GIVEN
    fetchSpy.mockResolvedValueOnce(shedResponse()).mockResolvedValueOnce(ok());

    // WHEN
    const response = await retryingFetch(TEST_URL, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    // THEN
    expect(response.status).toBe(200);
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(fetchSpy.mock.calls[1]?.[0]).toBe(TEST_URL);
  });

  it("lets init override the Request's method, as fetch does", async () => {
    // GIVEN a GET Request turned into a mutation by init, shed by something foreign
    fetchSpy.mockResolvedValue(foreignRateLimitResponse());
    const request = new Request(TEST_URL);

    // WHEN
    const response = await retryingFetch(request, { method: "POST", body: "{}" });

    // THEN
    expect(response.status).toBe(429);
    expect(fetchSpy).toHaveBeenCalledOnce();
  });

  it("lets an explicit null init signal clear the Request's signal, as fetch does", async () => {
    // GIVEN a Request whose own signal aborts mid-flight
    const controller = new AbortController();
    fetchSpy.mockImplementationOnce(async () => {
      controller.abort();
      return shedResponse();
    });
    fetchSpy.mockResolvedValueOnce(ok());
    const request = new Request(TEST_URL, { signal: controller.signal });

    // WHEN
    const response = await retryingFetch(request, { signal: null });

    // THEN
    expect(response.status).toBe(200);
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });

  it("rejects with the signal's reason instead of replaying when the caller aborts", async () => {
    // GIVEN
    const controller = new AbortController();
    fetchSpy.mockImplementation(async () => {
      controller.abort(new Error("gone"));
      return shedResponse();
    });

    // WHEN
    const pending = retryingFetch(TEST_URL, { signal: controller.signal });

    // THEN
    await expect(pending).rejects.toThrow("gone");
    expect(fetchSpy).toHaveBeenCalledOnce();
  });

  it("honours a Request's own signal", async () => {
    // GIVEN
    const controller = new AbortController();
    fetchSpy.mockImplementation(async () => {
      controller.abort();
      return shedResponse();
    });

    // WHEN
    const pending = retryingFetch(new Request(TEST_URL, { signal: controller.signal }));

    // THEN
    await expect(pending).rejects.toThrow();
    expect(fetchSpy).toHaveBeenCalledOnce();
  });
});
