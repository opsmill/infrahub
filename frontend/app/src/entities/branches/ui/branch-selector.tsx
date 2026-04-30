import { Icon } from "@iconify-icon/react";
import { Button, LinkButton } from "@infrahub/ui";
import { ArrowUpRightIcon, ChevronsUpDownIcon, PlusIcon } from "lucide-react";
import { useQueryState } from "nuqs";
import React from "react";
import {
  type ButtonProps as AriaButtonProps,
  Collection,
  ListLayout,
  useFilter,
  Virtualizer,
} from "react-aria-components";

import { constructPath } from "@/shared/api/rest/fetch";
import { Autocomplete } from "@/shared/components/aria/autocomplete";
import { ListBox, ListBoxItem, ListBoxLoadMoreItem } from "@/shared/components/aria/list-box";
import { Popover, PopoverDialog, PopoverTrigger } from "@/shared/components/aria/popover";
import { Separator } from "@/shared/components/aria/separator";
import { Tooltip } from "@/shared/components/aria/tooltip";
import { Row } from "@/shared/components/container";
import { QSP } from "@/shared/config/qsp";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import type { BranchListItem } from "@/entities/branches/domain/branch.mappers";
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
        className="w-64 px-2 data-pressed:scale-100"
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

        <ChevronsUpDownIcon />
      </Button>

      <Popover className="w-(--trigger-width)">
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
  const { data, hasNextPage, fetchNextPage, isFetchingNextPage } = useGetBranchesPaginated();
  const { setCurrentBranch } = useCurrentBranch();
  const [, setBranchInQueryString] = useQueryState(QSP.BRANCH);
  const { contains } = useFilter({ sensitivity: "base" });
  const { isAuthenticated } = useAuth();
  const [search, setSearch] = React.useState("");
  const trimmedSearch = search.trim();
  const branches = data?.pages.flat() ?? [];

  function handleBranchChange(branch: BranchListItem) {
    setBranchInQueryString(branch.is_default ? null : branch.name);
    setCurrentBranch(branch);
    closePopover();
  }

  return (
    <>
      <Autocomplete
        inputValue={search}
        onInputChange={setSearch}
        filter={(textValue, input) =>
          textValue === CREATE_BRANCH_ITEM_VALUE || contains(textValue, input)
        }
        suffix={<BranchFormTriggerButton onPress={() => openCreateForm(trimmedSearch)} />}
      >
        <Virtualizer
          layout={ListLayout}
          layoutOptions={{ rowHeight: 30, loaderHeight: 30, padding: 4 }}
        >
          <ListBox aria-label="branch list" emptyMessage="No branch found" className="max-h-125">
            <Collection items={branches}>
              {(branch) => (
                <ListBoxItem textValue={branch.name} onAction={() => handleBranchChange(branch)}>
                  <span className="truncate" title={branch.name}>
                    {branch.name}
                  </span>

                  <Row className="ml-auto">
                    {branch.is_default && <BranchDefaultBadge />}
                    <BranchStatusBadge status={branch.status} />
                    {branch.sync_with_git && <Icon icon="mdi:source-branch-sync" />}
                  </Row>
                </ListBoxItem>
              )}
            </Collection>

            {isAuthenticated && trimmedSearch && (
              <ListBoxItem
                textValue={CREATE_BRANCH_ITEM_VALUE}
                onAction={() => openCreateForm(trimmedSearch)}
                className="gap-1 whitespace-nowrap"
              >
                Create branch <span className="truncate font-semibold">{trimmedSearch}</span>
              </ListBoxItem>
            )}

            {hasNextPage && (
              <ListBoxLoadMoreItem isLoading={isFetchingNextPage} onLoadMore={fetchNextPage} />
            )}
          </ListBox>
        </Virtualizer>
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
        <ArrowUpRightIcon className="text-stone-500" />
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
        <PlusIcon className="size-5 text-stone-500" />
      </Button>
    </Tooltip>
  );
}
