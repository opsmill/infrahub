import {
  Autocomplete,
  Button,
  LinkButton,
  ListBox,
  ListBoxItem,
  ListBoxLoadMoreItem,
  Popover,
  PopoverDialog,
  PopoverTrigger,
  Tooltip,
} from "@infrahub/ui";
import { ArrowUpRightIcon, CheckIcon, ChevronsUpDownIcon, PlusIcon } from "lucide-react";
import React from "react";
import { type ButtonProps as AriaButtonProps, Collection } from "react-aria-components";

import { constructPath } from "@/shared/api/rest/fetch";
import { Separator } from "@/shared/components/aria/separator";
import { Row } from "@/shared/components/container";
import { Icon } from "@/shared/components/display/icon";
import { useDebounce } from "@/shared/hooks/useDebounce";

import { useAuth } from "@/entities/authentication/ui/auth-provider";
import type { BranchListItem } from "@/entities/branches/domain/model/branch";
import BranchCreateForm from "@/entities/branches/ui/branch-create-form";
import { BranchDefaultBadge } from "@/entities/branches/ui/branch-list-item/branch-default-badge";
import { BranchStatusBadge } from "@/entities/branches/ui/branch-list-item/branch-status-badge";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { useGetBranchesPaginated } from "@/entities/branches/ui/queries/get-branches.query";

// textValue for the "Create branch X" item.
// Whitelisted by the Autocomplete filter so it remains visible regardless of the current search input.
const CREATE_BRANCH_ITEM_VALUE = "__create_branch__";

export function BranchSelector() {
  const { currentBranch } = useCurrentBranch();
  const [isCreating, setIsCreating] = React.useState(false);
  const [initialBranchName, setInitialBranchName] = React.useState("");

  function openCreateForm(name: string) {
    setInitialBranchName(name);
    setIsCreating(true);
  }

  function closeCreateForm() {
    setIsCreating(false);
  }

  return (
    <PopoverTrigger
      onOpenChange={(open) => {
        if (open) closeCreateForm();
      }}
    >
      <Button
        variant="outline"
        size="sm"
        className="w-64 data-pressed:scale-100"
        data-testid="branch-selector-trigger"
      >
        <Row className="grow gap-1.5 overflow-hidden">
          <Icon icon="mdi:source-branch" className="shrink-0" />
          <span className="min-w-0 truncate" title={currentBranch.name}>
            {currentBranch.name}
          </span>
          <BranchStatusBadge status={currentBranch.status} className="ml-auto shrink-0" />
        </Row>

        <Separator orientation="vertical" />

        <ChevronsUpDownIcon className="ml-0.5" />
      </Button>

      <Popover placement="bottom start" width="min-trigger">
        <PopoverDialog>
          {({ close }) =>
            isCreating ? (
              <BranchCreateForm
                onCancel={closeCreateForm}
                onSuccess={() => {
                  closeCreateForm();
                  close();
                }}
                defaultBranchName={initialBranchName}
              />
            ) : (
              <BranchList closePopover={close} openCreateForm={openCreateForm} />
            )
          }
        </PopoverDialog>
      </Popover>
    </PopoverTrigger>
  );
}

interface BranchListProps {
  closePopover: () => void;
  openCreateForm: (name: string) => void;
}

function BranchList({ closePopover, openCreateForm }: BranchListProps) {
  const { currentBranch, setCurrentBranch } = useCurrentBranch();
  const { isAuthenticated } = useAuth();
  const [search, setSearch] = React.useState("");
  const trimmedSearch = search.trim();
  const debouncedSearch = useDebounce(trimmedSearch, 300);
  const { data, fetchNextPage, isFetchingNextPage, isPending } = useGetBranchesPaginated({
    filters: debouncedSearch ? [{ name: "any__value", value: debouncedSearch }] : undefined,
  });
  const branches = data?.pages.flat() ?? [];

  function handleBranchChange(branch: BranchListItem) {
    setCurrentBranch(branch);
    closePopover();
  }

  return (
    <>
      <Autocomplete
        inputValue={search}
        onInputChange={setSearch}
        suffix={<BranchFormTriggerButton onPress={() => openCreateForm(trimmedSearch)} />}
      >
        <ListBox
          virtualized
          aria-label="branch list"
          className="max-h-125"
          emptyMessage={isPending ? undefined : "No branch found"}
        >
          <Collection items={branches}>
            {(branch) => (
              <ListBoxItem textValue={branch.name} onAction={() => handleBranchChange(branch)}>
                <span className="truncate" title={branch.name}>
                  {branch.name}
                </span>

                <Row className="ml-auto">
                  {currentBranch.name === branch.name && <CheckIcon className="size-4 shrink-0" />}
                  {branch.is_default && <BranchDefaultBadge />}
                  {branch.sync_with_git && <Icon icon="mdi:source-branch-sync" />}
                  <BranchStatusBadge status={branch.status} />
                </Row>
              </ListBoxItem>
            )}
          </Collection>

          <ListBoxLoadMoreItem
            isLoading={isPending || isFetchingNextPage}
            onLoadMore={fetchNextPage}
          />

          {isAuthenticated && trimmedSearch && (
            <ListBoxItem
              textValue={CREATE_BRANCH_ITEM_VALUE}
              onAction={() => openCreateForm(trimmedSearch)}
              className="gap-1 whitespace-nowrap"
            >
              Create branch <span className="truncate font-semibold">{trimmedSearch}</span>
            </ListBoxItem>
          )}
        </ListBox>
      </Autocomplete>

      <Separator />

      <LinkButton
        variant="ghost"
        size="sm"
        href={constructPath("/branches")}
        className="m-1 flex grow justify-between"
        onPress={closePopover}
      >
        View all branches
        <ArrowUpRightIcon className="text-subtle-muted" />
      </LinkButton>
    </>
  );
}

export function BranchFormTriggerButton({ ...props }: AriaButtonProps) {
  const { isAuthenticated } = useAuth();

  return (
    <Tooltip message={isAuthenticated ? "Create branch" : "You need to be authenticated."}>
      <Button
        variant="ghost"
        shape="square"
        size="xxs"
        aria-label="Create branch"
        isDisabledAndFocusable={!isAuthenticated}
        data-testid="create-branch-button"
        {...props}
      >
        <PlusIcon className="size-5 text-subtle-muted" />
      </Button>
    </Tooltip>
  );
}
