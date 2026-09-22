import type { ReactElement } from "react";
import { toast } from "react-toastify";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { RetryOutcome } from "./policy";
import { notifyRetryScheduled } from "./retry-notice";

vi.mock("react-toastify", () => {
  const toastMock = Object.assign(vi.fn(), {
    isActive: vi.fn(() => false),
    update: vi.fn(),
    dismiss: vi.fn(),
  });
  return { toast: toastMock };
});

const toastMock = vi.mocked(toast);
const TOAST_ID = "alert-shed-retry";

function messageOf(render: unknown): string {
  return (render as ReactElement<{ message: string }>).props.message;
}

describe("notifyRetryScheduled", () => {
  // Every announced replay is settled again so the module's pending count is
  // back to zero before the next test.
  const handles: Array<(outcome: RetryOutcome) => void> = [];
  const announce = (delayMs: number) => {
    const handle = notifyRetryScheduled(delayMs);
    handles.push(handle);
    return handle;
  };

  afterEach(() => {
    for (const handle of handles.splice(0)) handle("abandoned");
    vi.useRealTimers();
    vi.clearAllMocks();
    toastMock.isActive.mockReturnValue(false);
  });

  it("says nothing about a wait too short to notice", () => {
    // GIVEN
    const delayMs = 300;

    // WHEN
    const settle = announce(delayMs);
    settle("abandoned");

    // THEN
    expect(toastMock).not.toHaveBeenCalled();
    expect(toastMock.update).not.toHaveBeenCalled();
    expect(toastMock.dismiss).not.toHaveBeenCalled();
  });

  it("tells the person how long the wait is, rounded up to whole seconds", () => {
    // GIVEN
    const delayMs = 1200;

    // WHEN
    announce(delayMs);

    // THEN
    expect(toastMock).toHaveBeenCalledOnce();
    const [render, options] = toastMock.mock.calls[0] ?? [];
    expect(messageOf(render)).toBe(
      "Infrahub is busy. Your request will be retried automatically in 2 seconds."
    );
    expect(options).toMatchObject({ toastId: TOAST_ID, autoClose: false });
  });

  it("uses the singular for a one-second wait", () => {
    // GIVEN
    const delayMs = 1000;

    // WHEN
    announce(delayMs);

    // THEN
    expect(messageOf(toastMock.mock.calls[0]?.[0])).toBe(
      "Infrahub is busy. Your request will be retried automatically in 1 second."
    );
  });

  it("updates the open notice instead of stacking another", () => {
    // GIVEN
    toastMock.isActive.mockReturnValue(true);

    // WHEN
    announce(5000);

    // THEN
    expect(toastMock).not.toHaveBeenCalled();
    expect(toastMock.update).toHaveBeenCalledOnce();
    const [id, options] = toastMock.update.mock.calls[0] ?? [];
    expect(id).toBe(TOAST_ID);
    expect(messageOf((options as { render?: unknown })?.render)).toBe(
      "Infrahub is busy. Your request will be retried automatically in 5 seconds."
    );
  });

  it("closes the notice at once when the only announced replay is abandoned", () => {
    // GIVEN
    const settle = announce(5000);

    // WHEN
    settle("abandoned");

    // THEN
    expect(toastMock.dismiss).toHaveBeenCalledExactlyOnceWith(TOAST_ID);
  });

  it("keeps the notice while another announced replay is still pending", () => {
    // GIVEN
    const first = announce(5000);
    announce(5000);

    // WHEN
    first("abandoned");

    // THEN
    expect(toastMock.dismiss).not.toHaveBeenCalled();
  });

  it("keeps the notice up briefly after the last replay fires", () => {
    // GIVEN
    vi.useFakeTimers();
    const settle = announce(2000);

    // WHEN
    settle("replayed");
    vi.advanceTimersByTime(499);

    // THEN
    expect(toastMock.dismiss).not.toHaveBeenCalled();
  });

  it("closes the notice once that grace has passed", () => {
    // GIVEN
    vi.useFakeTimers();
    const settle = announce(2000);
    settle("replayed");

    // WHEN
    vi.advanceTimersByTime(500);

    // THEN
    expect(toastMock.dismiss).toHaveBeenCalledExactlyOnceWith(TOAST_ID);
  });

  it("ignores a second report about the same replay", () => {
    // GIVEN a replay already reported as fired, its grace timer pending
    vi.useFakeTimers();
    const settle = announce(3000);
    settle("replayed");

    // WHEN
    settle("abandoned");
    vi.advanceTimersByTime(500);

    // THEN only the grace timer closes the notice, and only once
    expect(toastMock.dismiss).toHaveBeenCalledExactlyOnceWith(TOAST_ID);
  });
});
