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

const signedIn: AuthContextType = {
  accessToken: "token",
  isAuthenticated: true,
  setToken: () => {},
  user: { id: "user-1" },
};

describe("ApproveButton", () => {
  const initialProposedChange = store.get(proposedChangedState);

  beforeEach(() => {
    store.set(proposedChangedState, generateProposedChange());
  });

  afterAll(async () => {
    // Unmounted first, or the mounted button re-renders against an empty proposed change.
    await cleanup();
    store.set(proposedChangedState, initialProposedChange);
  });

  test("follows the cancel entry once the user has approved", async () => {
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
});
