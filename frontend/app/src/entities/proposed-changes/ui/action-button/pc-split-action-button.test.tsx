import { describe, expect, test, vi } from "vitest";
import { userEvent } from "vitest/browser";

import { render } from "../../../../../tests/components/render";
import { initPointerTracking } from "../../../../../tests/components/utils";
import { PcSplitActionButton } from "./pc-split-action-button";

const unavailableMerge = {
  action: "merge",
  available: false,
  unavailability_reason: "The proposed change has failing checks",
};

describe("PcSplitActionButton", () => {
  test("runs the action when the main button is pressed", async () => {
    // GIVEN
    const onPress = vi.fn();
    const component = await render(
      <PcSplitActionButton label="Merge" variant="active" onPress={onPress} />
    );

    // WHEN
    await component.getByRole("button", { name: "Merge" }).click();

    // THEN
    expect(onPress).toHaveBeenCalledOnce();
  });

  test("disables an unavailable action and keeps its picker chevron enabled", async () => {
    // WHEN
    const component = await render(
      <PcSplitActionButton
        label="Merge"
        variant="active"
        onPress={vi.fn()}
        availability={unavailableMerge}
        onOpenMenu={vi.fn()}
      />
    );

    // THEN
    await expect.element(component.getByRole("button", { name: "Merge" })).toBeDisabled();
    await expect.element(component.getByRole("button", { name: "More actions" })).toBeEnabled();
  });

  test("shows why an action is unavailable when the pointer rests on it", async () => {
    // GIVEN
    const component = await render(
      <PcSplitActionButton
        label="Merge"
        variant="active"
        onPress={vi.fn()}
        availability={unavailableMerge}
        onOpenMenu={vi.fn()}
      />
    );

    // WHEN
    await initPointerTracking(component.locator);
    await component.getByRole("button", { name: "Merge" }).hover();

    // THEN
    await expect
      .element(component.getByRole("tooltip", { name: "The proposed change has failing checks" }))
      .toBeVisible();
  });

  test("shows why an action is unavailable when it receives keyboard focus", async () => {
    // GIVEN
    const component = await render(
      <PcSplitActionButton
        label="Merge"
        variant="active"
        onPress={vi.fn()}
        availability={unavailableMerge}
        onOpenMenu={vi.fn()}
      />
    );

    // WHEN
    await userEvent.keyboard("{Tab}");

    // THEN
    await expect.element(component.getByRole("button", { name: "Merge" })).toHaveFocus();
    await expect
      .element(component.getByRole("tooltip", { name: "The proposed change has failing checks" }))
      .toBeVisible();
  });

  test("does not run an unavailable action from the keyboard", async () => {
    // GIVEN
    const onPress = vi.fn();
    const component = await render(
      <PcSplitActionButton
        label="Merge"
        variant="active"
        onPress={onPress}
        availability={unavailableMerge}
      />
    );
    await userEvent.keyboard("{Tab}");
    await expect.element(component.getByRole("button", { name: "Merge" })).toHaveFocus();

    // WHEN
    await userEvent.keyboard("{Enter}");
    await userEvent.keyboard(" ");

    // THEN
    expect(onPress).not.toHaveBeenCalled();
  });

  test("keeps an available action enabled", async () => {
    // GIVEN
    const availability = { action: "merge", available: true, unavailability_reason: null };

    // WHEN
    const component = await render(
      <PcSplitActionButton
        label="Merge"
        variant="active"
        onPress={vi.fn()}
        availability={availability}
      />
    );

    // THEN
    await expect.element(component.getByRole("button", { name: "Merge" })).toBeEnabled();
  });

  test("disables both buttons while the action is pending", async () => {
    // GIVEN
    const onOpenMenu = vi.fn();

    // WHEN
    const component = await render(
      <PcSplitActionButton label="Merge" variant="active" onOpenMenu={onOpenMenu} isPending />
    );

    // THEN
    await expect.element(component.getByRole("button", { name: "Merge" })).toBeDisabled();
    await expect.element(component.getByRole("button", { name: "More actions" })).toBeDisabled();
  });

  test("opens the action picker from the More actions chevron", async () => {
    // GIVEN
    const onOpenMenu = vi.fn();
    const component = await render(
      <PcSplitActionButton label="Merge" variant="active" onOpenMenu={onOpenMenu} />
    );
    const chevron = component.getByRole("button", { name: "More actions" });

    // WHEN
    await chevron.click();

    // THEN
    expect(onOpenMenu).toHaveBeenCalledOnce();
    await expect
      .element(chevron)
      .toHaveAttribute("data-testid", "proposed-change-action-button-select");
  });

  test("leaves the picker chevron without an accessible name when asked", async () => {
    // GIVEN
    const onOpenMenu = vi.fn();

    // WHEN
    const component = await render(
      <PcSplitActionButton label="Open" variant="primary" onOpenMenu={onOpenMenu} isMenuUnnamed />
    );

    // THEN
    const chevron = component.getByTestId("proposed-change-action-button-select");
    await expect.element(chevron).toBeEnabled();
    await expect.element(chevron).not.toHaveAttribute("aria-label");
  });

  test("submits the enclosing form from a submit button", async () => {
    // GIVEN
    const onSubmit = vi.fn();
    const component = await render(
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}
      >
        <PcSplitActionButton label="Open" variant="primary" type="submit" />
      </form>
    );

    // WHEN
    await component.getByRole("button", { name: "Open" }).click();

    // THEN
    expect(onSubmit).toHaveBeenCalledOnce();
  });

  test.each([
    { layout: "fill", height: 48 },
    { layout: "fit", height: 36 },
  ] as const)("sizes both buttons for the $layout layout", async ({ layout, height }) => {
    // GIVEN
    const onOpenMenu = vi.fn();

    // WHEN
    const component = await render(
      <div className="flex h-12">
        <PcSplitActionButton
          label="Merge"
          variant="active"
          onOpenMenu={onOpenMenu}
          layout={layout}
        />
      </div>
    );

    // THEN
    const main = component.getByRole("button", { name: "Merge" }).element();
    const chevron = component.getByRole("button", { name: "More actions" }).element();
    expect(main.getBoundingClientRect().height).toBe(height);
    expect(chevron.getBoundingClientRect().height).toBe(height);
  });
});
