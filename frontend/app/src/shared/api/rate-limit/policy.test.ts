import { afterEach, describe, expect, it, vi } from "vitest";

import { shedResponse } from "../../../../tests/fake/shed-response";
import { MAX_RETRIES, nextDelayMs, parseRetryAfter, sendWithRateLimitRetry } from "./policy";

const ok = () => new Response(null, { status: 200 });

// Pins the jitter so a delay is exactly the advice or exactly the backoff ceiling.
const noJitter = () => 0;

describe("parseRetryAfter", () => {
  it("reads the delta-seconds form as milliseconds", () => {
    // GIVEN
    const header = "5";

    // WHEN
    const wait = parseRetryAfter(header);

    // THEN
    expect(wait).toBe(5000);
  });

  it("tolerates surrounding whitespace", () => {
    // GIVEN
    const header = "  5  ";

    // WHEN
    const wait = parseRetryAfter(header);

    // THEN
    expect(wait).toBe(5000);
  });

  it("reads the HTTP-date form as the remaining wait", () => {
    // GIVEN
    const now = Date.parse("2026-01-01T00:00:00Z");
    const header = new Date(now + 2000).toUTCString();

    // WHEN
    const wait = parseRetryAfter(header, now);

    // THEN
    expect(wait).toBe(2000);
  });

  it("floors an HTTP-date already in the past to zero", () => {
    // GIVEN
    const now = Date.parse("2026-01-01T00:00:00Z");
    const header = new Date(now - 60_000).toUTCString();

    // WHEN
    const wait = parseRetryAfter(header, now);

    // THEN
    expect(wait).toBe(0);
  });

  it.each([null, undefined, "", "   ", "later", "-5"])("returns null for %o", (header) => {
    // GIVEN
    const unparseable = header;

    // WHEN
    const wait = parseRetryAfter(unparseable);

    // THEN
    expect(wait).toBeNull();
  });
});

describe("nextDelayMs", () => {
  it("never returns less than the server advised", () => {
    // GIVEN
    const advised = "5";

    // WHEN
    const delay = nextDelayMs(0, advised, noJitter);

    // THEN
    expect(delay).toBe(5000);
  });

  it("spreads concurrently-shed requests by jittering above the advice", () => {
    // GIVEN
    const advised = "5";
    const maxJitter = () => 1;

    // WHEN
    const delay = nextDelayMs(0, advised, maxJitter);

    // THEN
    expect(delay).toBe(5500);
  });

  it("clamps an advised wait to the backoff ceiling, as the SDK does", () => {
    // GIVEN
    const escalatedAdvice = "30";

    // WHEN
    const delay = nextDelayMs(0, escalatedAdvice, noJitter);

    // THEN
    expect(delay).toBe(10_000);
  });

  it("falls back to full-jitter exponential backoff when no advice is given", () => {
    // GIVEN
    const maxJitter = () => 1;

    // WHEN
    const delays = [0, 1, 2].map((attempt) => nextDelayMs(attempt, null, maxJitter));

    // THEN
    expect(delays).toEqual([300, 600, 1200]);
  });

  it("can draw zero from the full-jitter range", () => {
    // GIVEN
    const attempt = 2;

    // WHEN
    const delay = nextDelayMs(attempt, null, noJitter);

    // THEN
    expect(delay).toBe(0);
  });

  it("clamps a computed backoff to the ceiling", () => {
    // GIVEN
    const lateAttempt = 20;
    const maxJitter = () => 1;

    // WHEN
    const delay = nextDelayMs(lateAttempt, null, maxJitter);

    // THEN
    expect(delay).toBe(10_000);
  });
});

describe("sendWithRateLimitRetry", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns a non-429 response without replaying it", async () => {
    // GIVEN
    const send = vi.fn(async () => new Response(null, { status: 500 }));

    // WHEN
    const response = await sendWithRateLimitRetry(send);

    // THEN
    expect(send).toHaveBeenCalledOnce();
    expect(response.status).toBe(500);
  });

  it("replays a 429 and returns the response that succeeds", async () => {
    // GIVEN
    const send = vi
      .fn<() => Promise<Response>>()
      .mockResolvedValueOnce(shedResponse())
      .mockResolvedValueOnce(ok());

    // WHEN
    const response = await sendWithRateLimitRetry(send, { random: noJitter });

    // THEN
    expect(send).toHaveBeenCalledTimes(2);
    expect(response.status).toBe(200);
  });

  it("has not replayed before the advised wait elapses", async () => {
    // GIVEN
    vi.useFakeTimers();
    const send = vi
      .fn<() => Promise<Response>>()
      .mockResolvedValueOnce(shedResponse({ "Retry-After": "1" }))
      .mockResolvedValueOnce(ok());
    const pending = sendWithRateLimitRetry(send, { random: noJitter });

    // WHEN
    await vi.advanceTimersByTimeAsync(999);

    // THEN
    expect(send).toHaveBeenCalledOnce();
    // The race settles with the probe only while `pending` is still unsettled.
    await expect(Promise.race([pending, Promise.resolve("still waiting")])).resolves.toBe(
      "still waiting"
    );
  });

  it("replays once the advised wait has elapsed", async () => {
    // GIVEN
    vi.useFakeTimers();
    const send = vi
      .fn<() => Promise<Response>>()
      .mockResolvedValueOnce(shedResponse({ "Retry-After": "1" }))
      .mockResolvedValueOnce(ok());
    const pending = sendWithRateLimitRetry(send, { random: noJitter });

    // WHEN
    await vi.advanceTimersByTimeAsync(1000);

    // THEN
    await expect(pending).resolves.toHaveProperty("status", 200);
    expect(send).toHaveBeenCalledTimes(2);
  });

  it("gives the 429 back once the retry budget is spent", async () => {
    // GIVEN
    const send = vi.fn(async () => shedResponse());

    // WHEN
    const response = await sendWithRateLimitRetry(send, { random: noJitter });

    // THEN
    expect(send).toHaveBeenCalledTimes(MAX_RETRIES + 1);
    expect(response.status).toBe(429);
  });

  it("stops when the next wait would run past the retry window", async () => {
    // GIVEN an 8s advice: one replay fits the 15s window, a second would land at 16s
    vi.useFakeTimers();
    const send = vi.fn(async () => shedResponse({ "Retry-After": "8" }));
    const pending = sendWithRateLimitRetry(send, { random: noJitter });

    // WHEN
    await vi.advanceTimersByTimeAsync(8000);

    // THEN
    await expect(pending).resolves.toHaveProperty("status", 429);
    expect(send).toHaveBeenCalledTimes(2);
  });

  it("does not replay when the caller rules the response out", async () => {
    // GIVEN
    const send = vi.fn(async () => shedResponse());

    // WHEN
    const response = await sendWithRateLimitRetry(send, {
      random: noJitter,
      canReplay: () => false,
    });

    // THEN
    expect(send).toHaveBeenCalledOnce();
    expect(response.status).toBe(429);
  });

  it("reports the wait it has decided on before replaying", async () => {
    // GIVEN
    vi.useFakeTimers();
    const send = vi
      .fn<() => Promise<Response>>()
      .mockResolvedValueOnce(shedResponse({ "Retry-After": "2" }))
      .mockResolvedValueOnce(ok());
    const onRetryScheduled = vi.fn();

    // WHEN
    const pending = sendWithRateLimitRetry(send, { random: noJitter, onRetryScheduled });
    await vi.advanceTimersByTimeAsync(0);

    // THEN
    expect(onRetryScheduled).toHaveBeenCalledWith({ attempt: 0, delayMs: 2000 });
    expect(send).toHaveBeenCalledOnce();
    // The race settles with the probe only while the replay is still waiting.
    await expect(Promise.race([pending, Promise.resolve("still waiting")])).resolves.toBe(
      "still waiting"
    );
  });

  it("tells the reporter a replay was sent once its wait has elapsed", async () => {
    // GIVEN
    vi.useFakeTimers();
    const send = vi
      .fn<() => Promise<Response>>()
      .mockResolvedValueOnce(shedResponse({ "Retry-After": "1" }))
      .mockResolvedValueOnce(ok());
    const settle = vi.fn();
    const pending = sendWithRateLimitRetry(send, {
      random: noJitter,
      onRetryScheduled: () => settle,
    });

    // WHEN
    await vi.advanceTimersByTimeAsync(1000);

    // THEN
    await expect(pending).resolves.toHaveProperty("status", 200);
    expect(settle).toHaveBeenCalledExactlyOnceWith("replayed");
  });

  it("tells the reporter a replay was abandoned when the wait is aborted", async () => {
    // GIVEN
    vi.useFakeTimers();
    const controller = new AbortController();
    const send = vi.fn(async () => shedResponse({ "Retry-After": "10" }));
    const settle = vi.fn();
    const pending = sendWithRateLimitRetry(send, {
      random: noJitter,
      signal: controller.signal,
      onRetryScheduled: () => settle,
    });
    await vi.advanceTimersByTimeAsync(0);

    // WHEN
    controller.abort(new Error("gone"));

    // THEN
    await expect(pending).rejects.toThrow("gone");
    expect(settle).toHaveBeenCalledExactlyOnceWith("abandoned");
  });

  it("does not report a response it will not replay", async () => {
    // GIVEN a 429 on every attempt, so the last one is handed back unreplayed
    const send = vi.fn(async () => shedResponse());
    const onRetryScheduled = vi.fn();

    // WHEN
    await sendWithRateLimitRetry(send, { random: noJitter, onRetryScheduled });

    // THEN
    expect(onRetryScheduled).toHaveBeenCalledTimes(MAX_RETRIES);
  });

  it("rejects with the signal's reason instead of replaying a request that was already aborted", async () => {
    // GIVEN
    const send = vi.fn(async () => shedResponse());
    const signal = AbortSignal.abort(new Error("gone"));

    // WHEN
    const pending = sendWithRateLimitRetry(send, { random: noJitter, signal });

    // THEN
    await expect(pending).rejects.toThrow("gone");
    expect(send).toHaveBeenCalledOnce();
  });

  it("rejects with an AbortError when aborted mid-wait, as fetch does", async () => {
    // GIVEN
    vi.useFakeTimers();
    const controller = new AbortController();
    const send = vi.fn(async () => shedResponse({ "Retry-After": "10" }));
    const pending = sendWithRateLimitRetry(send, { random: noJitter, signal: controller.signal });
    await vi.advanceTimersByTimeAsync(0);

    // WHEN
    controller.abort();

    // THEN
    const outcome = await pending.catch((error: unknown) => error);
    expect(outcome).toBeInstanceOf(DOMException);
    expect(outcome).toHaveProperty("name", "AbortError");
    expect(send).toHaveBeenCalledOnce();
  });

  it("rejects without waiting when the abort landed while the response was in flight", async () => {
    // GIVEN a 10s advice, so a missed abort would hold this test past its timeout
    const controller = new AbortController();
    const send = vi.fn(async () => {
      controller.abort(new Error("gone"));
      return shedResponse({ "Retry-After": "10" });
    });

    // WHEN
    const pending = sendWithRateLimitRetry(send, { random: noJitter, signal: controller.signal });

    // THEN
    await expect(pending).rejects.toThrow("gone");
    expect(send).toHaveBeenCalledOnce();
  });
});
