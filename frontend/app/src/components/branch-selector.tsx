import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { QSP } from "@/config/qsp";
import { Branch } from "@/generated/graphql";
import { branchesState, currentBranchAtom } from "@/state/atoms/branches.atom";
import { branchesToSelectOptions } from "@/utils/branches";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai/index";
import { useEffect, useState } from "react";
import { StringParam, useQueryParam } from "use-query-params";

import { ComboboxItem } from "@/components/ui/combobox";
import { Command, CommandEmpty, CommandInput, CommandList } from "@/components/ui/command";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { useAuth } from "@/hooks/useAuth";
import { constructPath } from "@/utils/fetch";
import { useSetAtom } from "jotai";
import { Button, ButtonWithTooltip, LinkButton } from "./buttons/button-primitive";
import BranchCreateForm from "./form/branch-create-form";

export default function BranchSelector() {
  const currentBranch = useAtomValue(currentBranchAtom);
  const [isOpen, setIsOpen] = useState(false);
  const [displayForm, setDisplayForm] = useState(false);

  useEffect(() => {
    if (isOpen) graphqlClient.refetchQueries({ include: ["GetBranches"] });
  }, [isOpen]);

  return (
    <Popover
      open={isOpen}
      onOpenChange={(open) => {
        setDisplayForm(false);
        setIsOpen(open);
      }}
    >
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className="h-8 w-[205px] border-neutral-200 rounded-lg p-0 shadow-none"
          data-testid="branch-selector-trigger"
        >
          <div className="inline-flex items-center gap-1.5 px-3 flex-grow border-r h-full truncate">
            <Icon icon="mdi:source-branch" />
            <span className="truncate">{currentBranch?.name}</span>
          </div>

          <Icon icon="mdi:chevron-down" className="text-2xl px-3" />
        </Button>
      </PopoverTrigger>

      <PopoverContent align="start">
        {displayForm ? (
          <BranchCreateForm
            onCancel={() => {
              setDisplayForm(false);
            }}
            onSuccess={() => {
              setDisplayForm(false);
              setIsOpen(false);
            }}
            data-testid="branch-create-form"
          />
        ) : (
          <BranchSelect setPopoverOpen={setIsOpen} setFormOpen={setDisplayForm} />
        )}
      </PopoverContent>
    </Popover>
  );
}

function BranchSelect({
  setPopoverOpen,
  setFormOpen,
}: {
  setPopoverOpen: (open: boolean) => void;
  setFormOpen: (open: boolean) => void;
}) {
  const branches = useAtomValue(branchesState);
  const setCurrentBranch = useSetAtom(currentBranchAtom);
  const [, setBranchInQueryString] = useQueryParam(QSP.BRANCH, StringParam);

  const handleBranchChange = (branch: Branch) => {
    if (branch.is_default) {
      setBranchInQueryString(undefined); // undefined is needed to remove a parameter from the QSP
    } else {
      setBranchInQueryString(branch.name);
    }
    setCurrentBranch(branch);
    setPopoverOpen(false);
  };

  return (
    <>
      <Command
        style={{
          minWidth: "var(--radix-popover-trigger-width)",
          maxHeight: "min(var(--radix-popover-content-available-height), 500px)",
        }}
      >
        <div className="flex gap-2 mb-2">
          <CommandInput
            autoFocus
            className="bg-neutral-100 text-neutral-800 rounded-lg border-none h-8 flex-grow"
            placeholder="Search"
            data-testid="branch-search-input"
          />

          <BranchFormTriggerButton setOpen={setFormOpen} />
        </div>

        <CommandList className="p-0" data-testid="branch-list">
          <CommandEmpty>No branch found</CommandEmpty>
          {branchesToSelectOptions(branches).map((branch) => (
            <BranchOption
              key={branch.name}
              branch={branch}
              onChange={() => handleBranchChange(branch)}
            />
          ))}
        </CommandList>
      </Command>
      <div className="p-2 pb-0 border-t border-neutral-200 -mx-2 mt-2">
        <LinkButton
          to={constructPath("/branches")}
          variant="ghost"
          size="sm"
          className="w-full text-xs justify-start"
          onClick={() => setPopoverOpen(false)}
        >
          View all branches
        </LinkButton>
      </div>
    </>
  );
}

function BranchOption({ branch, onChange }: { branch: Branch; onChange: () => void }) {
  const currentBranch = useAtomValue(currentBranchAtom);

  return (
    <ComboboxItem
      className="p-2"
      selectedValue={currentBranch?.name}
      onSelect={onChange}
      value={branch.name}
    >
      <div className="truncate flex items-center w-full">
        <span className="truncate">{branch.name}</span>

        <div className="ml-auto inline-flex items-center gap-1">
          {branch.is_default && (
            <span className="rounded border text-gray-400 px-1.5 text-xs">default</span>
          )}
          {branch.sync_with_git && (
            <Icon icon="mdi:source-branch-sync" className="text-sm text-gray-400" />
          )}
        </div>
      </div>
    </ComboboxItem>
  );
}

export const BranchFormTriggerButton = ({ setOpen }: { setOpen: (open: boolean) => void }) => {
  const { isAuthenticated } = useAuth();

  return (
    <ButtonWithTooltip
      disabled={!isAuthenticated}
      tooltipEnabled={!isAuthenticated}
      tooltipContent={"You need to be authenticated."}
      className="h-8 w-8 shadow-none"
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.stopPropagation();
          setOpen(true);
        }
      }}
      onClick={(e) => {
        e.stopPropagation();
        setOpen(true);
      }}
      data-testid="create-branch-button"
    >
      <Icon icon="mdi:plus" />
    </ButtonWithTooltip>
  );
};
