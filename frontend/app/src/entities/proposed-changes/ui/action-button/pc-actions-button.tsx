import { useAuth } from "@/entities/authentication/ui/useAuth";
import { Combobox, ComboboxContent } from "@/shared/components/ui/combobox";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";
import { ReactElement, useState } from "react";
import { ActionComboboxList } from "./pc-actions-combobox-list";
import { ApproveButton } from "./pc-approve-button";
import { OpenButton } from "./pc-close-button";
import { MergeButton } from "./pc-merge-button";
import { PcPlaceholderButton } from "./pc-placeholder-button";
import { RejectButton } from "./pc-reject-button";
import { ProposedChangeActionButtonProps } from "./types";

type ActionButtonComponent = (props: ProposedChangeActionButtonProps) => ReactElement;

const actionsListMapping: Record<string, ActionButtonComponent> = {
  approve: ({ setOpen }) => <ApproveButton setOpen={setOpen} />,
  reject: ({ setOpen }) => <RejectButton setOpen={setOpen} />,
  merge: ({ setOpen }) => <MergeButton setOpen={setOpen} />,
  close: ({ setOpen }) => <OpenButton setOpen={setOpen} />,
};

export const PcActionButton = () => {
  const auth = useAuth();

  const [open, setOpen] = useState(false);
  const [action, setAction] = useState<string>("approve");

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div className={classNames(inputStyle, "flex p-0 border-0 ")}>
          {auth?.user?.id ? actionsListMapping?.[action]?.({ setOpen }) : <PcPlaceholderButton />}
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
