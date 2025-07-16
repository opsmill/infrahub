import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { Button, ButtonProps } from "@/shared/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Combobox, ComboboxContent } from "@/shared/components/ui/combobox";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";
import { capitalizeFirstLetter } from "@/shared/utils/string";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import { toast } from "react-toastify";
import { useUpdateReview } from "../../domain/update-review.mutation";
import { ActionComboboxList } from "./actions-combobox-list";

interface PcActionButtonProps extends ButtonProps {
  proposedChangeId: string;
  approvers: Array<any>;
  state: "closed" | "open" | "merged";
}

export const PcActionButton = ({ proposedChangeId }: PcActionButtonProps) => {
  const [open, setOpen] = useState(false);
  const [action, setAction] = useState("approve");

  const { mutateAsync: updateObjectMutateAsync, isPending: isObjectUpdatePending } =
    useUpdateReview({
      onSuccess: async () => {
        await graphqlClient.reFetchObservableQueries();
        toast(<Alert type={ALERT_TYPES.SUCCESS} message="Proposed change updated!" />);
      },
      onError: async () => {
        await graphqlClient.reFetchObservableQueries();
        toast(
          <Alert
            type={ALERT_TYPES.SUCCESS}
            message="An error occured while updating the proposed changes"
          />
        );
      },
    });

  const { mutateAsync: updateApprovalMutateAsync, isPending: isApprovalUpdatePending } =
    useUpdateReview({
      onSuccess: async () => {
        await graphqlClient.reFetchObservableQueries();
        toast(<Alert type={ALERT_TYPES.SUCCESS} message="Proposed change approved!" />);
      },
      onError: async () => {
        await graphqlClient.reFetchObservableQueries();
        toast(
          <Alert
            type={ALERT_TYPES.SUCCESS}
            message="An error occured while approving the proposed changes"
          />
        );
      },
    });

  const handleAction = () => {
    switch (action) {
      case "cancel-reject":
      case "reject":
      case "cancel-approve":
      case "approve": {
        return updateApprovalMutateAsync({
          proposedChangeId,
          decision: action,
        });
      }
      case "merge":
      case "close": {
        return updateObjectMutateAsync({
          proposedChangeId,
          decision: action,
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
            {capitalizeFirstLetter(action)}
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
