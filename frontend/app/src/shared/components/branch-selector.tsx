import { Icon } from "@iconify-icon/react";
import { useCommandState } from "cmdk";
import { useQueryState } from "nuqs";
import { useState } from "react";

import type { Branch } from "@/shared/api/graphql/generated/graphql";
import { constructPath } from "@/shared/api/rest/fetch";
import { ComboboxItem } from "@/shared/components/ui/combobox";
import {
  Command,
  CommandEmpty,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/shared/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import { QSP } from "@/shared/config/qsp";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { useGetBranches } from "@/entities/branches/domain/get-branches.query";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { branchesToSelectOptions } from "@/entities/branches/utils";

import { Button, ButtonWithTooltip, LinkButton } from "./buttons/button-primitive";
import BranchCreateForm from "./form/branch-create-form";

type DisplayForm = {
  open: boolean;
  defaultBranchName?: string;
};

export default function BranchSelector() {
  const { currentBranch } = useCurrentBranch();
  const [isOpen, setIsOpen] = useState(false);
  const [displayForm, setDisplayForm] = useState<DisplayForm>({ open: false });

  return (
    <Popover
      open={isOpen}
      onOpenChange={(open) => {
        setDisplayForm({ open: false });
        setIsOpen(open);
      }}
    >
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className="h-8 w-[205px] rounded-lg border-neutral-200 p-0 shadow-none"
          data-testid="branch-selector-trigger"
        >
          <div className="inline-flex h-full grow items-center gap-1.5 truncate border-gray-200 border-r px-3">
            <Icon icon="mdi:source-branch" />
            <span className="truncate">{currentBranch.name}</span>
          </div>

          <Icon icon="mdi:chevron-down" className="px-3 text-2xl" />
        </Button>
      </PopoverTrigger>

      <PopoverContent align="start">
        {displayForm.open ? (
          <BranchCreateForm
            onCancel={() => setDisplayForm({ open: false })}
            onSuccess={() => {
              setDisplayForm({ open: false });
              setIsOpen(false);
            }}
            defaultBranchName={displayForm.defaultBranchName}
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
  setFormOpen: (displayForm: DisplayForm) => void;
}) {
  const { data: branches = [] } = useGetBranches();
  const { setCurrentBranch } = useCurrentBranch();
  const [, setBranchInQueryString] = useQueryState(QSP.BRANCH);

  const handleBranchChange = (branch: Branch) => {
    setBranchInQueryString(branch.is_default ? null : branch.name);
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
        <div className="mb-2 flex gap-2">
          <CommandInput
            autoFocus
            className="h-8 grow rounded-lg border-none bg-neutral-100 text-neutral-800"
            placeholder="Search"
            data-testid="branch-search-input"
          />

          <BranchFormTriggerButton setOpen={setFormOpen} />
        </div>

        <CommandList className="p-0" data-testid="branch-list">
          <BranchNotFound
            onSelect={(defaultBranchName) => setFormOpen({ open: true, defaultBranchName })}
          />

          {branchesToSelectOptions(branches).map((branch) => (
            <BranchOption
              key={branch.name}
              branch={branch}
              onChange={() => handleBranchChange(branch)}
            />
          ))}
        </CommandList>
      </Command>
      <div className="-mx-2 mt-2 border-neutral-200 border-t p-2 pb-0">
        <LinkButton
          to={constructPath("/branches")}
          variant="ghost"
          size="sm"
          className="w-full justify-start text-xs"
          onClick={() => setPopoverOpen(false)}
        >
          View all branches
        </LinkButton>
      </div>
    </>
  );
}

function BranchOption({ branch, onChange }: { branch: Branch; onChange: () => void }) {
  const { currentBranch } = useCurrentBranch();

  return (
    <ComboboxItem
      className="p-2"
      selectedValue={currentBranch.name}
      onSelect={onChange}
      value={branch.name}
    >
      <div className="flex w-full items-center truncate">
        <span className="truncate">{branch.name}</span>

        <div className="ml-auto inline-flex items-center gap-1">
          {branch.is_default && (
            <span className="rounded-sm border border-gray-200 px-1.5 text-gray-400 text-xs">
              default
            </span>
          )}
          {branch.sync_with_git && (
            <Icon icon="mdi:source-branch-sync" className="text-gray-400 text-sm" />
          )}
        </div>
      </div>
    </ComboboxItem>
  );
}

export const BranchFormTriggerButton = ({
  setOpen,
}: {
  setOpen: (displayForm: DisplayForm) => void;
}) => {
  const { isAuthenticated } = useAuth();

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setOpen({ open: true });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.stopPropagation();
      setOpen({ open: true });
    }
  };

  return (
    <ButtonWithTooltip
      disabled={!isAuthenticated}
      tooltipEnabled={!isAuthenticated}
      tooltipContent="You need to be authenticated."
      className="h-8 w-8 shadow-none"
      onKeyDown={handleKeyDown}
      onClick={handleClick}
      data-testid="create-branch-button"
    >
      <Icon icon="mdi:plus" />
    </ButtonWithTooltip>
  );
};

const BranchNotFound = ({ onSelect }: { onSelect: (branchName: string) => void }) => {
  const filteredCount = useCommandState((state) => state.filtered.count);
  const search = useCommandState((state) => state.search);
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) return <CommandEmpty>No branch found</CommandEmpty>;
  if (filteredCount !== 0) return null;

  return (
    <CommandItem
      forceMount
      value="create"
      onSelect={() => onSelect(search)}
      className="gap-1 truncate text-neutral-600"
    >
      Create branch <span className="font-semibold text-neutral-800">{search}</span>
    </CommandItem>
  );
};
