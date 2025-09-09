import { useAtomValue } from "jotai";
import { forwardRef } from "react";

import { ComboboxItem, ComboboxList } from "@/shared/components/ui/combobox";
import { Tooltip } from "@/shared/components/ui/tooltip";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";
import { usePcActionsContext } from "@/entities/proposed-changes/ui/pc-actions-permissions-context";
import { hasUserApprovedProposedChange } from "@/entities/proposed-changes/utils/has-user-approved-proposed-change";
import { hasUserRejectedProposedChange } from "@/entities/proposed-changes/utils/has-user-rejected-proposed-change";

type ActionItem = { value: string; name: string; isDisabled?: boolean; message: string | null };

export interface ReviewComboboxListProps {
  onSelect: (value: string) => void;
  value?: string | null;
}

export const ReviewComboboxList = forwardRef<HTMLDivElement, ReviewComboboxListProps>(
  ({ value, onSelect }, ref) => {
    const auth = useAuth();
    const { approve, reject } = usePcActionsContext();
    const proposedChangesDetails = useAtomValue(proposedChangedState);

    const actionsList: Record<string, ActionItem> = {
      approve: {
        value: "approve",
        name:
          auth.user && hasUserApprovedProposedChange(proposedChangesDetails, auth.user)
            ? "Cancel Approval"
            : "Approve",
        isDisabled: !approve.available,
        message: approve.unavailability_reason,
      },
      reject: {
        value: "reject",
        name:
          auth.user && hasUserRejectedProposedChange(proposedChangesDetails, auth.user)
            ? "Cancel Reject"
            : "Reject",
        isDisabled: !reject.available,
        message: reject.unavailability_reason,
      },
    };

    return (
      <ComboboxList ref={ref}>
        {Object.entries(actionsList).map(([, action]) => {
          if (action.isDisabled) {
            return (
              <Tooltip
                enabled
                content={action.message}
                className="whitespace-pre"
                key={action.value}
              >
                <span className="ml-5 flex cursor-default select-none items-center gap-2 truncate rounded-md px-2 py-1.5 text-sm opacity-50 outline-hidden">
                  {action.name}
                </span>
              </Tooltip>
            );
          }

          return (
            <ComboboxItem
              key={action.value}
              value={action.value}
              selectedValue={value}
              onSelect={() => onSelect(action.value)}
              className="cursor-pointer"
            >
              <span className="truncate">{action.name}</span>
            </ComboboxItem>
          );
        })}
      </ComboboxList>
    );
  }
);
