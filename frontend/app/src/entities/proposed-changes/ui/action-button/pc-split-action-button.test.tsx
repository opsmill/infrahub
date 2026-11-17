import { useState } from "react";
import { FormProvider, useForm } from "react-hook-form";
import { afterAll, beforeEach, describe, expect, test, vi } from "vitest";
import { cleanup } from "vitest-browser-react";

import { store } from "@/shared/stores";

import { AuthContext, type AuthContextType } from "@/entities/authentication/ui/auth-provider";
import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";
import { PcActionsContext } from "@/entities/proposed-changes/ui/pc-actions-permissions-context";

import { render } from "../../../../../tests/components/render";
import {
  generateProposedChange,
  generateProposedChangeActions,
} from "../../../../../tests/fake/proposed-change";
import { ApproveButton } from "./pc-approve-button";
import { CloseButton } from "./pc-close-button";
import { PcPlaceholderButton } from "./pc-placeholder-button";
import { PcSplitActionButton } from "./pc-split-action-button";
import { PcStateButton } from "./pc-state-button";

const signedIn: AuthContextType = {
  accessToken: "token",
  isAuthenticated: true,
  setToken: () => {},
  user: { id: "user-1" },
};

function CreateFormState({ onSubmit }: { onSubmit: () => void }) {
  const form = useForm();
  const [state, setState] = useState("open");

  return (
    <AuthContext value={signedIn}>
      <FormProvider {...form}>
        <form onSubmit={form.handleSubmit(onSubmit)}>
          <PcStateButton state={state} setState={setState} />
        </form>
      </FormProvider>
    </AuthContext>
  );
}

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
    // GIVEN
    const availability = {
      action: "merge",
      available: false,
      unavailability_reason: "The proposed change has failing checks",
    };

    // WHEN
    const component = await render(
      <PcSplitActionButton
        label="Merge"
        variant="active"
        onPress={vi.fn()}
        availability={availability}
        onOpenMenu={vi.fn()}
      />
    );

    // THEN
    await expect.element(component.getByRole("button", { name: "Merge" })).toBeDisabled();
    await expect.element(component.getByRole("button", { name: "More actions" })).toBeEnabled();
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

describe("PcSplitActionButton callers", () => {
  const initialProposedChange = store.get(proposedChangedState);

  beforeEach(() => {
    store.set(proposedChangedState, generateProposedChange());
  });

  afterAll(async () => {
    // Unmounted first, or the mounted buttons re-render against an empty proposed change.
    await cleanup();
    store.set(proposedChangedState, initialProposedChange);
  });

  test("the login placeholder disables both buttons and offers no picker", async () => {
    // GIVEN
    const placeholder = <PcPlaceholderButton />;

    // WHEN
    const component = await render(placeholder);

    // THEN
    await expect.element(component.getByRole("button", { name: "Please login" })).toBeDisabled();
    const chevron = component.getByRole("button").nth(1);
    await expect.element(chevron).toBeDisabled();
    await expect.element(chevron).not.toHaveAttribute("data-testid");
    await expect.element(chevron).not.toHaveAttribute("aria-label");
  });

  test("the close button is disabled while closing is unavailable", async () => {
    // GIVEN
    const actions = generateProposedChangeActions({
      close: { available: false, unavailability_reason: "Only open proposed changes can close" },
    });

    // WHEN
    const component = await render(
      <PcActionsContext value={actions}>
        <CloseButton setOpen={vi.fn()} />
      </PcActionsContext>
    );

    // THEN
    await expect.element(component.getByRole("button", { name: "Close" })).toBeDisabled();
    await expect
      .element(component.getByTestId("proposed-change-action-button-select"))
      .toBeEnabled();
  });

  test("the approve button follows the cancel entry once the user has approved", async () => {
    // GIVEN
    store.set(
      proposedChangedState,
      generateProposedChange({
        approved_by: { edges: [{ node: { id: "user-1", __typename: "CoreAccount" } }] },
      })
    );
    const actions = generateProposedChangeActions({
      cancelApprove: { available: false, unavailability_reason: "The review is locked" },
    });

    // WHEN
    const component = await render(
      <AuthContext value={signedIn}>
        <PcActionsContext value={actions}>
          <ApproveButton setOpen={vi.fn()} />
        </PcActionsContext>
      </AuthContext>
    );

    // THEN
    await expect.element(component.getByRole("button", { name: "Cancel Approve" })).toBeDisabled();
  });

  test("the create form submits from the Open button", async () => {
    // GIVEN
    const onSubmit = vi.fn();
    const component = await render(<CreateFormState onSubmit={onSubmit} />);

    // WHEN
    await component.getByRole("button", { name: "Open", exact: true }).click();

    // THEN
    await vi.waitFor(() => expect(onSubmit).toHaveBeenCalledOnce());
  });

  test("the create form relabels its submit button after choosing Draft", async () => {
    // GIVEN
    const component = await render(<CreateFormState onSubmit={vi.fn()} />);
    await component.getByTestId("proposed-change-action-button-select").click();

    // WHEN
    await component.getByRole("option", { name: "Draft", exact: true }).click();

    // THEN
    await expect
      .element(component.getByRole("button", { name: "Open a draft", exact: true }))
      .toBeVisible();
  });
});
