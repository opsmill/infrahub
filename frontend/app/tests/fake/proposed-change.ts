import type { ActionAvailability } from "@/shared/api/graphql/generated/types";

import type { ProposedChangeDetail } from "@/entities/proposed-changes/domain/model/proposed-change";
import type { PcActionsContextType } from "@/entities/proposed-changes/ui/pc-actions-permissions-context";

type ProposedChangeActionKey = keyof PcActionsContextType;

const ACTION_NAMES: Record<ProposedChangeActionKey, string> = {
  approve: "approve",
  cancelApprove: "cancel-approve",
  close: "close",
  merge: "merge",
  reject: "reject",
  cancelReject: "cancel-reject",
  setDraft: "set-draft",
  unsetDraft: "unset-draft",
};

export const generateProposedChange = (
  overrides?: Partial<ProposedChangeDetail>
): ProposedChangeDetail => {
  return {
    id: "18a6c3b4-2a5e-4c1f-9d0b-c51171c1ef01",
    __typename: "CoreProposedChange",
    display_label: "Add edge routers",
    name: { value: "Add edge routers" },
    description: { value: "", updated_at: "2024-12-12T09:36:44.968848Z" },
    source_branch: { value: "edge-routers" },
    destination_branch: { value: "main" },
    state: { value: "open" },
    is_draft: { value: false },
    approved_by: { edges: [] },
    rejected_by: { edges: [] },
    reviewers: { edges: [] },
    comments: { count: 0 },
    ...overrides,
  };
};

/** Every action is available unless an override says otherwise. */
export const generateProposedChangeActions = (
  overrides: Partial<Record<ProposedChangeActionKey, Partial<ActionAvailability>>> = {}
): Record<ProposedChangeActionKey, ActionAvailability> => {
  const entry = (key: ProposedChangeActionKey): ActionAvailability => ({
    __typename: "ActionAvailability",
    action: ACTION_NAMES[key],
    available: true,
    unavailability_reason: null,
    ...overrides[key],
  });

  return {
    approve: entry("approve"),
    cancelApprove: entry("cancelApprove"),
    close: entry("close"),
    merge: entry("merge"),
    reject: entry("reject"),
    cancelReject: entry("cancelReject"),
    setDraft: entry("setDraft"),
    unsetDraft: entry("unsetDraft"),
  };
};
