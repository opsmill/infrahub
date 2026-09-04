import { afterEach, describe, expect, it, vi } from "vitest";

import { MAX_RETRIES, nextDelayMs, parseRetryAfter, sendWithRateLimitRetry } from "./policy";

function shedResponse(headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify({ data: null, errors: [{ extensions: { code: 429 } }] }), {
    status: 429,
    headers,
  });
}

describe("parseRetryAfter", () => {
  it("reads the delta-seconds form as milliseconds", () => {
    expect(parseRetryAfter("5")).toBe(5000);
  });

  it("tolerates surrounding whitespace", () => {
    expect(parseRetryAfter("  5  ")).toBe(5000);
  });

  it("reads the HTTP-date form as the remaining wait", () => {
    const now = Date.parse("2026-01-01T00:00:00Z");
    expect(parseRetryAfter(new Date(now + 2000).toUTCString(), now)).toBe(2000);
  });

  it("floors an HTTP-date already in the past to zero", () => {
    const now = Date.parse("2026-01-01T00:00:00Z");
    expect(parseRetryAfter(new Date(now - 60_000).toUTCString(), now)).toBe(0);
  });

  it.each([null, undefined, "", "   ", "later", "-5"])("returns null for %o", (header) => {
    expect(parseRetryAfter(header)).toBeNull();
  });
});

describe("nextDelayMs", () => {
  it("never returns less than the server advised", () => {
    expect(nextDelayMs(0, "5", () => 0)).toBe(5000);
  });

  it("spreads concurrently-shed requests by jittering above the advice", () => {
    expect(nextDelayMs(0, "5", () => 1)).toBe(5500);
  });

  it("falls back to full-jitter exponential backoff when no advice is given", () => {
    expect(nextDelayMs(0, null, () => 1)).toBe(300);
    expect(nextDelayMs(1, null, () => 1)).toBe(600);
    expect(nextDelayMs(2, null, () => 1)).toBe(1200);
    // Full jitter draws from [0, ceiling], so the same attempt can come back at 0.
    expect(nextDelayMs(2, null, () => 0)).toBe(0);
  });

  it("clamps a computed backoff to the ceiling", () => {
    expect(nextDelayMs(20, null, () => 1)).toBe(10_000);
  });
});

describe("sendWithRateLimitRetry", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns a non-429 response without replaying it", async () => {
    const send = vi.fn(async () => new Response(null, { status: 500 }));

    const response = await sendWithRateLimitRetry(send);

    expect(send).toHaveBeenCalledOnce();
    expect(response.status).toBe(500);
  });

  it("replays a 429 and returns the response that succeeds", async () => {
    const send = vi
      .fn<() => Promise<Response>>()
      .mockResolvedValueOnce(shedResponse())
      .mockResolvedValueOnce(new Response(null, { status: 200 }));

    const response = await sendWithRateLimitRetry(send, { random: () => 0 });

    expect(send).toHaveBeenCalledTimes(2);
    expect(response.status).toBe(200);
  });

  it("waits the advised Retry-After before replaying", async () => {
    vi.useFakeTimers();
    const send = vi
      .fn<() => Promise<Response>>()
      .mockResolvedValueOnce(shedResponse({ "Retry-After": "1" }))
      .mockResolvedValueOnce(new Response(null, { status: 200 }));

    const pending = sendWithRateLimitRetry(send, { random: () => 0 });

    await vi.advanceTimersByTimeAsync(0);
    expect(send).toHaveBeenCalledOnce();

    await vi.advanceTimersByTimeAsync(999);
    expect(send).toHaveBeenCalledOnce();

    await vi.advanceTimersByTimeAsync(1);
    expect(await pending).toHaveProperty("status", 200);
    expect(send).toHaveBeenCalledTimes(2);
  });

  it("gives the 429 back once the retry budget is spent", async () => {
    const send = vi.fn(async () => shedResponse());

    const response = await sendWithRateLimitRetry(send, { random: () => 0 });

    expect(send).toHaveBeenCalledTimes(MAX_RETRIES + 1);
    expect(response.status).toBe(429);
  });

  it("gives up when the advised wait would outlast the retry window", async () => {
    const send = vi.fn(async () => shedResponse({ "Retry-After": "30" }));

    const response = await sendWithRateLimitRetry(send, { random: () => 0 });

    expect(send).toHaveBeenCalledOnce();
    expect(response.status).toBe(429);
  });

  it("does not replay when the caller rules the response out", async () => {
    const send = vi.fn(async () => shedResponse());

    const response = await sendWithRateLimitRetry(send, {
      random: () => 0,
      canReplay: () => false,
    });

    expect(send).toHaveBeenCalledOnce();
    expect(response.status).toBe(429);
  });

  it("does not replay a request that was already aborted", async () => {
    const send = vi.fn(async () => shedResponse());

    const response = await sendWithRateLimitRetry(send, {
      random: () => 0,
      signal: AbortSignal.abort(),
    });

    expect(send).toHaveBeenCalledOnce();
    expect(response.status).toBe(429);
  });

  it("stops waiting as soon as the request is aborted mid-wait", async () => {
    vi.useFakeTimers();
    const controller = new AbortController();
    const send = vi.fn(async () => shedResponse({ "Retry-After": "10" }));

    const pending = sendWithRateLimitRetry(send, { random: () => 0, signal: controller.signal });
    await vi.advanceTimersByTimeAsync(0);
    controller.abort();

    expect(await pending).toHaveProperty("status", 429);
    expect(send).toHaveBeenCalledOnce();
  });
});
