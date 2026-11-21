import type React from "react";
import { afterAll, afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { cleanup } from "vitest-browser-react";

import { store } from "@/shared/stores";

import { AuthContext, type AuthContextType } from "@/entities/authentication/ui/auth-provider";
import type { ProposedChangeDetail } from "@/entities/proposed-changes/domain/model/proposed-change";
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

const signedInUserEdges = { edges: [{ node: { id: "user-1", __typename: "CoreAccount" } }] };

/** Only the entry each option follows is unavailable, so the option is dimmed only when it reads that entry. */
const optionsFollowingAnotherEntry: {
  name: string;
  picker: React.ReactElement;
  proposedChange: Partial<ProposedChangeDetail>;
  actions: Parameters<typeof generateProposedChangeActions>[0];
  option: string;
  entry: string;
}[] = [
  {
    name: "a user who approved",
    picker: <PcReviewButton />,
    proposedChange: { approved_by: signedInUserEdges },
    actions: { approve: { available: false, unavailability_reason: "Approvals are locked" } },
    option: "Cancel Approval",
    entry: "approve",
  },
  {
    name: "a user who rejected",
    picker: <PcReviewButton />,
    proposedChange: { rejected_by: signedInUserEdges },
    actions: { reject: { available: false, unavailability_reason: "Rejections are locked" } },
    option: "Cancel Reject",
    entry: "reject",
  },
  {
    name: "a draft",
    picker: <PcActionButton />,
    proposedChange: { is_draft: { value: true } },
    actions: { unsetDraft: { available: false, unavailability_reason: "Drafts are locked" } },
    option: "Open",
    entry: "unsetDraft",
  },
];

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

  test.each(optionsFollowingAnotherEntry)(
    "lists $option for $name as unavailable when the $entry action is",
    async ({ picker, proposedChange, actions, option }) => {
      // GIVEN
      store.set(proposedChangedState, generateProposedChange(proposedChange));
      vi.mocked(getProposedChangeAvailableActions).mockResolvedValue(
        generateProposedChangeActions(actions)
      );
      const component = await renderPicker(picker);

      // WHEN
      await component.getByRole("button", { name: "More actions" }).click();

      // THEN
      await expect.element(component.getByText(option, { exact: true })).toBeVisible();
      expect(component.getByRole("option", { name: option }).query()).toBeNull();
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
