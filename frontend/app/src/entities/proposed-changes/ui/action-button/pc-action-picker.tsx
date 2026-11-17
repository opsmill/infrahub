import { type ComponentType, useState } from "react";

import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Combobox, ComboboxContent } from "@/shared/components/ui/combobox";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { PcPlaceholderButton } from "@/entities/proposed-changes/ui/action-button/pc-placeholder-button";
import type { ProposedChangeActionButtonProps } from "@/entities/proposed-changes/ui/action-button/types";

export interface PcActionPickerListProps<TAction extends string> {
  value: TAction;
  onSelect: (action: TAction) => void;
}

interface PcActionPickerProps<TAction extends string> {
  /** True while the available actions load. */
  isLoading: boolean;
  defaultAction: NoInfer<TAction>;
  buttons: Record<TAction, ComponentType<ProposedChangeActionButtonProps>>;
  list: ComponentType<PcActionPickerListProps<TAction>>;
}

export function PcActionPicker<TAction extends string>({
  isLoading,
  defaultAction,
  buttons,
  list: List,
}: PcActionPickerProps<TAction>) {
  const auth = useAuth();

  const [open, setOpen] = useState(false);
  const [action, setAction] = useState<TAction>(defaultAction);

  const ActionButton: ComponentType<ProposedChangeActionButtonProps> = buttons[action];

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div className={classNames(inputStyle, "flex border-0 p-0")}>
          {isLoading && <LoadingIndicator />}
          {!isLoading && auth?.user?.id ? (
            <ActionButton setOpen={setOpen} />
          ) : (
            <PcPlaceholderButton />
          )}
        </div>
      </PopoverTrigger>
      <ComboboxContent fitTriggerWidth={false}>
        <List
          value={action}
          onSelect={(selectedAction) => {
            setOpen(false);
            setAction(selectedAction);
          }}
        />
      </ComboboxContent>
    </Combobox>
  );
}
