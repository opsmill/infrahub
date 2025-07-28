import { useAuth } from "@/entities/authentication/ui/useAuth";
import { Button } from "@/shared/components/buttons/button-primitive";
import { Combobox, ComboboxContent } from "@/shared/components/ui/combobox";
import { PopoverTrigger } from "@/shared/components/ui/popover";
import { classNames } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import { useFormContext } from "react-hook-form";
import { PcPlaceholderButton } from "./pc-placeholder-button";
import { StateComboboxList, statesList } from "./pc-state-combobox-list";

export const PcStateButton = ({ state = "open", setState }) => {
  const auth = useAuth();
  const { formState } = useFormContext();

  const isLoading = formState.isSubmitting || formState.isValidating;

  const [open, setOpen] = useState(false);

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div className={classNames("flex p-0 border-0")}>
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
                {statesList[state].message}
              </Button>

              <Button
                className="rounded-l-none border-l-0 h-9"
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
