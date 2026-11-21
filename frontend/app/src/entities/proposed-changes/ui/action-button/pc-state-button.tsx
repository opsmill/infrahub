import { useState } from "react";
import { useFormContext } from "react-hook-form";

import { Combobox, ComboboxContent } from "@/shared/components/ui/combobox";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { classNames } from "@/shared/utils/common";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import { PcActionComboboxList } from "@/entities/proposed-changes/ui/action-button/pc-action-combobox-list";
import { PcPlaceholderButton } from "@/entities/proposed-changes/ui/action-button/pc-placeholder-button";
import { PcSplitActionButton } from "@/entities/proposed-changes/ui/action-button/pc-split-action-button";
import { pcStatesList } from "@/entities/proposed-changes/ui/action-button/pc-states-list";

const stateItems = Object.values(pcStatesList);

interface PcStateButtonProps {
  state?: string;
  setState: (state: string) => void;
}

export const PcStateButton = ({ state = "open", setState }: PcStateButtonProps) => {
  const auth = useAuth();
  const { formState } = useFormContext();

  const isLoading = formState.isSubmitting || formState.isValidating;

  const [open, setOpen] = useState(false);

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div className={classNames("flex border-0 p-0")}>
          {auth?.user?.id ? (
            <PcSplitActionButton
              label={state && pcStatesList[state] && pcStatesList[state].message}
              variant={"primary"}
              type="submit"
              isPending={isLoading}
              onOpenMenu={() => {
                setOpen(true);
              }}
              isMenuUnnamed
              layout="fit"
            />
          ) : (
            <PcPlaceholderButton />
          )}
        </div>
      </PopoverTrigger>
      <ComboboxContent fitTriggerWidth={false}>
        <PcActionComboboxList
          items={stateItems}
          value={state}
          onSelect={(action) => {
            setOpen(false);
            setState(action);
          }}
        />
      </ComboboxContent>
    </Combobox>
  );
};
