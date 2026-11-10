import { describe, expect, test, vi } from "vitest";
import { userEvent } from "vitest/browser";
import { render } from "vitest-browser-react";

import { FloatingPanel } from "./floating-panel";

describe("FloatingPanel", () => {
  test("renders title, description and body", async () => {
    // GIVEN
    const component = await render(
      <FloatingPanel title="Filters" description="Refine results" onClose={() => {}}>
        <p>Body content</p>
      </FloatingPanel>
    );

    // THEN
    await expect.element(component.getByRole("heading", { name: "Filters" })).toBeVisible();
    await expect.element(component.getByText("Refine results")).toBeVisible();
    await expect.element(component.getByText("Body content")).toBeVisible();
  });

  test("renders nothing when isOpen is false", async () => {
    // GIVEN
    const component = await render(
      <FloatingPanel title="Filters" isOpen={false} onClose={() => {}}>
        <p>Body content</p>
      </FloatingPanel>
    );

    // THEN
    expect(component.container.querySelector("h2")).toBeNull();
    expect(component.container.querySelector("p")).toBeNull();
  });

  test("calls onClose when the close button is pressed", async () => {
    // GIVEN
    const onClose = vi.fn<() => void>();
    const component = await render(
      <FloatingPanel title="Filters" onClose={onClose}>
        <p>Body</p>
      </FloatingPanel>
    );

    // WHEN
    await component.getByRole("button", { name: "Close panel" }).click();

    // THEN
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("when dismissable, Escape calls onClose", async () => {
    // GIVEN
    const onClose = vi.fn<() => void>();
    await render(
      <FloatingPanel title="Filters" onClose={onClose} dismissable>
        <p>Body</p>
      </FloatingPanel>
    );

    // WHEN
    await userEvent.keyboard("{Escape}");

    // THEN
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test("when NOT dismissable, Escape does not call onClose", async () => {
    // GIVEN
    const onClose = vi.fn<() => void>();
    await render(
      <FloatingPanel title="Filters" onClose={onClose}>
        <p>Body</p>
      </FloatingPanel>
    );

    // WHEN
    await userEvent.keyboard("{Escape}");

    // THEN
    expect(onClose).not.toHaveBeenCalled();
  });
});
