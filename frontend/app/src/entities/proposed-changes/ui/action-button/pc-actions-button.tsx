import { Combobox, ComboboxContent } from "@/shared/components/ui/combobox";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";
import { ReactElement, useState } from "react";
import { ActionComboboxList } from "./actions-combobox-list";
import { ApproveButton } from "./approve-button";
import { OpenButton } from "./close-button";
import { MergeButton } from "./merge-button";
import { RejectButton } from "./reject-button";
import { ProposedChangeActionButtonProps } from "./types";

type ActionButtonComponent = (props: ProposedChangeActionButtonProps) => ReactElement;

const actionsListMapping: Record<string, ActionButtonComponent> = {
  approve: ({ setOpen }) => <ApproveButton setOpen={setOpen} />,
  reject: ({ setOpen }) => <RejectButton setOpen={setOpen} />,
  merge: ({ setOpen }) => <MergeButton setOpen={setOpen} />,
  close: ({ setOpen }) => <OpenButton setOpen={setOpen} />,
};

export const PcActionButton = () => {
  const [open, setOpen] = useState(false);
  const [action, setAction] = useState<string>("approve");

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div className={classNames(inputStyle, "flex p-0 border-0 ")}>
          {actionsListMapping?.[action]?.({ setOpen })}
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
