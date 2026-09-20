import { useRef } from "react";
import { describe, expect, test, vi } from "vitest";
import { userEvent } from "vitest/browser";
import { render } from "vitest-browser-react";

import { useDismiss } from "./use-dismiss";

function Harness({ onDismiss, active }: { onDismiss: (event: Event) => void; active?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useDismiss(ref, onDismiss, active);
  return (
    <div>
      <button type="button">outside</button>
      <div ref={ref}>
        <button type="button">inside</button>
      </div>
    </div>
  );
}

function HarnessWithTrigger({ onDismiss }: { onDismiss: (event: Event) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  useDismiss(ref, onDismiss, true, { ignoreRef: triggerRef });
  return (
    <div>
      <button type="button" ref={triggerRef}>
        trigger
      </button>
      <button type="button">other-outside</button>
      <div ref={ref}>
        <button type="button">inside</button>
      </div>
    </div>
  );
}

describe("useDismiss", () => {
  test("calls onDismiss when clicking outside the ref", async () => {
    // GIVEN
    const onDismiss = vi.fn<(event: Event) => void>();
    const component = await render(<Harness onDismiss={onDismiss} active />);

    // WHEN clicking outside
    await component.getByRole("button", { name: "outside" }).click();

    // THEN
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  test("does not call onDismiss when clicking inside the ref", async () => {
    // GIVEN
    const onDismiss = vi.fn<(event: Event) => void>();
    const component = await render(<Harness onDismiss={onDismiss} active />);

    // WHEN clicking inside
    await component.getByRole("button", { name: "inside" }).click();

    // THEN
    expect(onDismiss).not.toHaveBeenCalled();
  });

  test("calls onDismiss when pressing Escape", async () => {
    // GIVEN
    const onDismiss = vi.fn<(event: Event) => void>();
    await render(<Harness onDismiss={onDismiss} active />);

    // WHEN pressing Escape
    await userEvent.keyboard("{Escape}");

    // THEN
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  test("does not call onDismiss when pressing down on the ignored trigger", async () => {
    // GIVEN a panel whose external trigger is registered via ignoreRef
    const onDismiss = vi.fn<(event: Event) => void>();
    const component = await render(<HarnessWithTrigger onDismiss={onDismiss} />);

    // WHEN pressing the trigger (would otherwise read as an outside click)
    await component.getByRole("button", { name: "trigger" }).click();

    // THEN it is treated as inside, so no dismiss-then-reopen race
    expect(onDismiss).not.toHaveBeenCalled();
  });

  test("still calls onDismiss when clicking outside both the ref and the ignored trigger", async () => {
    // GIVEN
    const onDismiss = vi.fn<(event: Event) => void>();
    const component = await render(<HarnessWithTrigger onDismiss={onDismiss} />);

    // WHEN clicking elsewhere outside
    await component.getByRole("button", { name: "other-outside" }).click();

    // THEN
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  test("passes the triggering event to onDismiss", async () => {
    // GIVEN
    const onDismiss = vi.fn<(event: Event) => void>();
    await render(<Harness onDismiss={onDismiss} active />);

    // WHEN
    await userEvent.keyboard("{Escape}");

    // THEN the consumer receives the event (e.g. to stop propagation)
    expect(onDismiss).toHaveBeenCalledWith(expect.any(KeyboardEvent));
  });

  test("does nothing when active is false", async () => {
    // GIVEN
    const onDismiss = vi.fn<(event: Event) => void>();
    const component = await render(<Harness onDismiss={onDismiss} active={false} />);

    // WHEN clicking outside and pressing Escape
    await component.getByRole("button", { name: "outside" }).click();
    await userEvent.keyboard("{Escape}");

    // THEN
    expect(onDismiss).not.toHaveBeenCalled();
  });
});
