import { useAtomValue } from "jotai";
import { type ReactElement, useState } from "react";

import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Combobox, ComboboxContent } from "@/shared/components/ui/combobox";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { useGetProposedChangeAvailableActions } from "@/entities/proposed-changes/domain/get-proposed-change-available-actions.query";
import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";
import { ApproveButton } from "@/entities/proposed-changes/ui/action-button/pc-approve-button";
import { PcPlaceholderButton } from "@/entities/proposed-changes/ui/action-button/pc-placeholder-button";
import { RejectButton } from "@/entities/proposed-changes/ui/action-button/pc-reject-button";
import { ReviewComboboxList } from "@/entities/proposed-changes/ui/action-button/pc-review-combobox-list";
import type { ProposedChangeActionButtonProps } from "@/entities/proposed-changes/ui/action-button/types";
import { PcActionsContext } from "@/entities/proposed-changes/ui/pc-actions-permissions-context";

type ReviewButtonComponent = (props: ProposedChangeActionButtonProps) => ReactElement;

type Review = "approve" | "reject";

const actionsListMapping: Record<Review, ReviewButtonComponent> = {
  approve: ({ setOpen }) => <ApproveButton setOpen={setOpen} />,
  reject: ({ setOpen }) => <RejectButton setOpen={setOpen} />,
};

export const PcReviewButton = () => {
  const auth = useAuth();
  const proposedChange = useAtomValue(proposedChangedState);

  const { data, isPending } = useGetProposedChangeAvailableActions({
    proposedChangeId: proposedChange.id,
  });

  const [open, setOpen] = useState(false);
  const [action, setReview] = useState<Review>("approve");

  return (
    <PcActionsContext value={data}>
      <Combobox open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <div className={classNames(inputStyle, "flex border-0 p-0")}>
            {isPending && <LoadingIndicator />}
            {!isPending && auth?.user?.id ? (
              actionsListMapping?.[action]?.({ setOpen })
            ) : (
              <PcPlaceholderButton />
            )}
          </div>
        </PopoverTrigger>
        <ComboboxContent fitTriggerWidth={false}>
          <ReviewComboboxList
            value={action}
            onSelect={(action) => {
              setOpen(false);
              setReview(action as Review);
            }}
          />
        </ComboboxContent>
      </Combobox>
    </PcActionsContext>
  );
};
