import { useRef } from "react";
import { describe, expect, test, vi } from "vitest";
import { render } from "vitest-browser-react";
import { userEvent } from "vitest/browser";

import { useDismiss } from "./use-dismiss";

function Harness({ onDismiss, active }: { onDismiss: () => void; active?: boolean }) {
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

describe("useDismiss", () => {
  test("calls onDismiss when clicking outside the ref", async () => {
    // GIVEN
    const onDismiss = vi.fn();
    const component = await render(<Harness onDismiss={onDismiss} active />);

    // WHEN clicking outside
    await component.getByRole("button", { name: "outside" }).click();

    // THEN
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  test("does not call onDismiss when clicking inside the ref", async () => {
    // GIVEN
    const onDismiss = vi.fn();
    const component = await render(<Harness onDismiss={onDismiss} active />);

    // WHEN clicking inside
    await component.getByRole("button", { name: "inside" }).click();

    // THEN
    expect(onDismiss).not.toHaveBeenCalled();
  });

  test("calls onDismiss when pressing Escape", async () => {
    // GIVEN
    const onDismiss = vi.fn();
    await render(<Harness onDismiss={onDismiss} active />);

    // WHEN pressing Escape
    await userEvent.keyboard("{Escape}");

    // THEN
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  test("does nothing when active is false", async () => {
    // GIVEN
    const onDismiss = vi.fn();
    const component = await render(<Harness onDismiss={onDismiss} active={false} />);

    // WHEN clicking outside and pressing Escape
    await component.getByRole("button", { name: "outside" }).click();
    await userEvent.keyboard("{Escape}");

    // THEN
    expect(onDismiss).not.toHaveBeenCalled();
  });
});
