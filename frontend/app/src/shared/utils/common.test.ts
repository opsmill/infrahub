import { afterEach, describe, expect, it, vi } from "vitest";

import { waitFor } from "./common";

describe("waitFor", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("resolves once the delay has elapsed", async () => {
    // GIVEN
    vi.useFakeTimers();
    const pending = waitFor(1000);

    // WHEN
    await vi.advanceTimersByTimeAsync(1000);

    // THEN
    await expect(pending).resolves.toBeUndefined();
  });

  it("resolves at once when the signal is already aborted", async () => {
    // GIVEN fake timers, so a wait that did not short-circuit would never settle
    vi.useFakeTimers();
    const signal = AbortSignal.abort();

    // WHEN
    const pending = waitFor(10_000, signal);

    // THEN
    await expect(pending).resolves.toBeUndefined();
  });

  it("resolves as soon as the signal aborts mid-wait", async () => {
    // GIVEN
    vi.useFakeTimers();
    const controller = new AbortController();
    const pending = waitFor(10_000, controller.signal);

    // WHEN
    controller.abort();

    // THEN
    await expect(pending).resolves.toBeUndefined();
  });
});
