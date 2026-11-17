import type React from "react";
import { afterAll, afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { cleanup } from "vitest-browser-react";

import { store } from "@/shared/stores";

import { AuthContext, type AuthContextType } from "@/entities/authentication/ui/auth-provider";
import { getProposedChangeAvailableActions } from "@/entities/proposed-changes/domain/use-cases/get-proposed-change-available-actions";
import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";

import { render } from "../../../../../tests/components/render";
import {
  generateProposedChange,
  generateProposedChangeActions,
} from "../../../../../tests/fake/proposed-change";
import { PcActionButton } from "./pc-action-button";
import { PcReviewButton } from "./pc-review-button";

vi.mock("@/entities/proposed-changes/domain/use-cases/get-proposed-change-available-actions");

const signedIn: AuthContextType = {
  accessToken: "token",
  isAuthenticated: true,
  setToken: () => {},
  user: { id: "user-1" },
};

const signedOut: AuthContextType = {
  accessToken: "",
  isAuthenticated: false,
  setToken: () => {},
  user: null,
};

const renderPicker = (picker: React.ReactElement, auth = signedIn) =>
  render(<AuthContext value={auth}>{picker}</AuthContext>);

const pickers = [
  {
    name: "action",
    picker: <PcActionButton />,
    defaultLabel: "Merge",
    otherOption: "Close",
  },
  {
    name: "review",
    picker: <PcReviewButton />,
    defaultLabel: "Approve",
    otherOption: "Reject",
  },
];

describe("PcActionPicker", () => {
  const initialProposedChange = store.get(proposedChangedState);

  beforeEach(() => {
    store.set(proposedChangedState, generateProposedChange());
    vi.mocked(getProposedChangeAvailableActions).mockResolvedValue(generateProposedChangeActions());
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  afterAll(async () => {
    // Unmounted first, or the mounted buttons re-render against an empty proposed change.
    await cleanup();
    store.set(proposedChangedState, initialProposedChange);
  });

  test("shows the loading indicator while the available actions load", async () => {
    // GIVEN
    vi.mocked(getProposedChangeAvailableActions).mockReturnValue(new Promise(() => {}));

    // WHEN
    const component = await renderPicker(<PcActionButton />);

    // THEN
    await expect.element(component.getByRole("status")).toBeVisible();
  });

  test("shows a disabled login prompt to a signed-out user", async () => {
    // GIVEN
    const auth = signedOut;

    // WHEN
    const component = await renderPicker(<PcActionButton />, auth);

    // THEN
    await expect.element(component.getByRole("status")).not.toBeInTheDocument();
    await expect.element(component.getByRole("button", { name: "Please login" })).toBeDisabled();
  });

  test.each(pickers)(
    "starts the $name picker on $defaultLabel",
    async ({ picker, defaultLabel }) => {
      // GIVEN
      const auth = signedIn;

      // WHEN
      const component = await renderPicker(picker, auth);

      // THEN
      await expect
        .element(component.getByRole("button", { name: defaultLabel, exact: true }))
        .toBeEnabled();
    }
  );

  test.each(pickers)(
    "switches the $name picker to $otherOption",
    async ({ picker, otherOption }) => {
      // GIVEN
      const component = await renderPicker(picker);
      await component.getByRole("button", { name: "More actions" }).click();

      // WHEN
      await component.getByRole("option", { name: otherOption, exact: true }).click();

      // THEN
      await expect
        .element(component.getByRole("button", { name: otherOption, exact: true }))
        .toBeVisible();
    }
  );

  test("opens the action options from the second picker chevron on the details card", async () => {
    // GIVEN
    const component = await renderPicker(
      <>
        <PcReviewButton />
        <PcActionButton />
      </>
    );
    await expect.element(component.getByRole("button", { name: "Merge" })).toBeVisible();

    // WHEN
    await component.getByTestId("proposed-change-action-button-select").nth(1).click();

    // THEN
    await expect.element(component.getByRole("option", { name: "Move to draft" })).toBeVisible();
  });
});
