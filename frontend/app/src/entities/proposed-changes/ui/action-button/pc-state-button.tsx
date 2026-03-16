import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import { useFormContext } from "react-hook-form";

import { Button } from "@/shared/components/ui/button";
import { Combobox, ComboboxContent } from "@/shared/components/ui/combobox";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { classNames } from "@/shared/utils/common";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { pcStatesList } from "@/entities/proposed-changes/constants";
import { PcPlaceholderButton } from "@/entities/proposed-changes/ui/action-button/pc-placeholder-button";
import { StateComboboxList } from "@/entities/proposed-changes/ui/action-button/pc-state-combobox-list";

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
            <>
              <Button
                className="flex gap-2 rounded-r-none border-r-white"
                variant={"primary"}
                type="submit"
                onClick={(event) => {
                  event.stopPropagation();
                }}
                isLoading={isLoading}
                disabled={isLoading}
              >
                {state && pcStatesList[state] && pcStatesList[state].message}
              </Button>

              <Button
                className="h-9 rounded-l-none border-l-0"
                variant={"primary"}
                size={"sm"}
                onClick={() => {
                  setOpen(true);
                }}
                disabled={isLoading}
                data-testid="proposed-change-action-button-select"
              >
                <Icon icon="mdi:unfold-more-horizontal" />
              </Button>
            </>
          ) : (
            <PcPlaceholderButton />
          )}
        </div>
      </PopoverTrigger>
      <ComboboxContent fitTriggerWidth={false}>
        <StateComboboxList
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
