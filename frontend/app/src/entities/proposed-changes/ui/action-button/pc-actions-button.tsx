import { PROPOSED_CHANGES_OBJECT } from "@/config/constants";
import { useUpdateObjectMutation } from "@/entities/nodes/object/domain/update-object.mutation";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { Button, ButtonProps } from "@/shared/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Combobox, ComboboxContent } from "@/shared/components/ui/combobox";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import { toast } from "react-toastify";
import { PROPOSED_CHANGE_APPROVAL_ACTIONS, PROPOSED_CHANGE_STATE_ACTIONS } from "../../constant";
import { useUpdateReview } from "../../domain/update-review.mutation";
import { ActionComboboxList } from "./actions-combobox-list";

interface PcActionButtonProps extends ButtonProps {
  proposedChangeId: string;
  approvers: Array<any>;
  state: "closed" | "open" | "merged";
}

export const PcActionButton = ({ proposedChangeId }: PcActionButtonProps) => {
  const [open, setOpen] = useState(false);
  const [action, setAction] = useState(null);

  const { mutateAsync: updateObjectMutateAsync, isPending: isObjectUpdatePending } =
    useUpdateObjectMutation({
      onSuccess: async () => {
        await graphqlClient.reFetchObservableQueries();
        toast(
          <Alert
            type={ALERT_TYPES.SUCCESS}
            message={action?.value && PROPOSED_CHANGE_STATE_ACTIONS[action.value].successMessage}
          />
        );
      },
      onError: async () => {
        await graphqlClient.reFetchObservableQueries();
        toast(
          <Alert
            type={ALERT_TYPES.ERROR}
            message={action?.value && PROPOSED_CHANGE_STATE_ACTIONS[action.value].errorMessage}
          />
        );
      },
    });

  const { mutateAsync: updateApprovalMutateAsync, isPending: isApprovalUpdatePending } =
    useUpdateReview({
      onSuccess: async () => {
        await graphqlClient.reFetchObservableQueries();
        toast(
          <Alert
            type={ALERT_TYPES.SUCCESS}
            message={action?.value && PROPOSED_CHANGE_APPROVAL_ACTIONS[action.value].successMessage}
          />
        );
      },
      onError: async () => {
        await graphqlClient.reFetchObservableQueries();
        toast(
          <Alert
            type={ALERT_TYPES.ERROR}
            message={action?.value && PROPOSED_CHANGE_APPROVAL_ACTIONS[action.value].errorMessage}
          />
        );
      },
    });

  const handleAction = (event) => {
    event.stopPropagation();

    switch (action?.value) {
      case "cancel-reject":
      case "reject":
      case "cancel-approve":
      case "approve": {
        return updateApprovalMutateAsync({
          proposedChangeId,
          decision: PROPOSED_CHANGE_APPROVAL_ACTIONS[action.value].decision,
        });
      }
      case "merge":
      case "open":
      case "close": {
        return updateObjectMutateAsync({
          data: {
            id: proposedChangeId,
            state: {
              value: PROPOSED_CHANGE_STATE_ACTIONS[action.value].state,
            },
          },
          objectKind: PROPOSED_CHANGES_OBJECT,
        });
      }
    }
  };

  const isLoading = isApprovalUpdatePending || isObjectUpdatePending;

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div className={classNames(inputStyle, "flex p-0 border-0 ")}>
          <Button
            className="grow flex flex-wrap gap-2 h-full rounded-r-none border-r-white"
            onClick={handleAction}
            variant={"primary"}
            isLoading={isLoading}
            disabled={isLoading}
          >
            {action?.name}
          </Button>

          <Button
            className="h-full rounded-l-none border-l-0"
            variant={"primary"}
            size={"sm"}
            onClick={() => {
              setOpen(true);
            }}
            disabled={isLoading}
          >
            <Icon icon="mdi:unfold-more-horizontal" />
          </Button>
        </div>
      </PopoverTrigger>
      <ComboboxContent fitTriggerWidth={false}>
        <ActionComboboxList
          value={action}
          onSelect={(action) => {
            setOpen(false);
            setAction(action);
          }}
        />
      </ComboboxContent>
    </Combobox>
  );
};
