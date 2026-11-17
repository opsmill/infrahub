import type { ComponentType } from "react";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { hasUserApprovedProposedChange } from "@/entities/proposed-changes/domain/rules/has-user-approved-proposed-change";
import { hasUserRejectedProposedChange } from "@/entities/proposed-changes/domain/rules/has-user-rejected-proposed-change";
import {
  type PcActionComboboxItem,
  PcActionComboboxList,
} from "@/entities/proposed-changes/ui/action-button/pc-action-combobox-list";
import {
  PcActionPicker,
  type PcActionPickerListProps,
} from "@/entities/proposed-changes/ui/action-button/pc-action-picker";
import { ApproveButton } from "@/entities/proposed-changes/ui/action-button/pc-approve-button";
import { RejectButton } from "@/entities/proposed-changes/ui/action-button/pc-reject-button";
import type { ProposedChangeActionButtonProps } from "@/entities/proposed-changes/ui/action-button/types";
import { useProposedChange } from "@/entities/proposed-changes/ui/hooks/use-proposed-change";
import {
  PcActionsContext,
  usePcActionsContext,
} from "@/entities/proposed-changes/ui/pc-actions-permissions-context";
import { useGetProposedChangeAvailableActions } from "@/entities/proposed-changes/ui/queries/get-proposed-change-available-actions.query";

type Review = "approve" | "reject";

const reviewButtons: Record<Review, ComponentType<ProposedChangeActionButtonProps>> = {
  approve: ApproveButton,
  reject: RejectButton,
};

const ReviewComboboxList = ({ value, onSelect }: PcActionPickerListProps<Review>) => {
  const auth = useAuth();
  const { approve, reject } = usePcActionsContext();
  const proposedChangesDetails = useProposedChange();

  const items: PcActionComboboxItem<Review>[] = [
    {
      value: "approve",
      name:
        auth.user && hasUserApprovedProposedChange(proposedChangesDetails, auth.user)
          ? "Cancel Approval"
          : "Approve",
      availability: approve,
    },
    {
      value: "reject",
      name:
        auth.user && hasUserRejectedProposedChange(proposedChangesDetails, auth.user)
          ? "Cancel Reject"
          : "Reject",
      availability: reject,
    },
  ];

  return <PcActionComboboxList items={items} value={value} onSelect={onSelect} />;
};

export const PcReviewButton = () => {
  const proposedChange = useProposedChange();

  const { data, isPending } = useGetProposedChangeAvailableActions({
    proposedChangeId: proposedChange.id,
  });

  return (
    <PcActionsContext value={data}>
      <PcActionPicker
        isLoading={isPending}
        defaultAction="approve"
        buttons={reviewButtons}
        list={ReviewComboboxList}
      />
    </PcActionsContext>
  );
};
