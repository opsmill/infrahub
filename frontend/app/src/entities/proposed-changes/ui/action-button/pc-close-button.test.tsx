import { afterAll, beforeEach, describe, expect, test, vi } from "vitest";
import { cleanup } from "vitest-browser-react";

import { store } from "@/shared/stores";

import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";
import { PcActionsContext } from "@/entities/proposed-changes/ui/pc-actions-permissions-context";

import { render } from "../../../../../tests/components/render";
import {
  generateProposedChange,
  generateProposedChangeActions,
} from "../../../../../tests/fake/proposed-change";
import { CloseButton } from "./pc-close-button";

describe("CloseButton", () => {
  const initialProposedChange = store.get(proposedChangedState);

  beforeEach(() => {
    store.set(proposedChangedState, generateProposedChange());
  });

  afterAll(async () => {
    // Unmounted first, or the mounted button re-renders against an empty proposed change.
    await cleanup();
    store.set(proposedChangedState, initialProposedChange);
  });

  test("is disabled while closing is unavailable", async () => {
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
});
