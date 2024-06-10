import { DateDisplay } from "@/components/display/date-display";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { QSP } from "@/config/qsp";
import { Branch } from "@/generated/graphql";
import { usePermission } from "@/hooks/usePermission";
import { branchesState, currentBranchAtom } from "@/state/atoms/branches.atom";
import { branchesToSelectOptions } from "@/utils/branches";
import { classNames } from "@/utils/common";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai/index";
import React from "react";
import { StringParam, useQueryParam } from "use-query-params";
import { ButtonWithTooltip } from "./buttons/button-with-tooltip";
import { SelectButton } from "./buttons/select-button";
import BranchCreateForm from "./form/branch-create-form";
import { SelectOption } from "./inputs/select";

const getBranchIcon = (branch: Branch | null, active?: Boolean) =>
  branch && (
    <>
      {branch.has_schema_changes && (
        <Icon
          icon={"mdi:file-alert"}
          className={classNames(active ? "text-custom-white" : "text-gray-500")}
        />
      )}

      {branch.is_default && (
        <Icon
          icon={"mdi:shield-star"}
          className={classNames(active ? "text-custom-white" : "text-gray-500")}
        />
      )}

      {branch.sync_with_git && (
        <Icon
          icon={"mdi:git"}
          className={classNames(active ? "text-custom-white" : "text-red-400")}
        />
      )}
    </>
  );

export default function BranchSelector() {
  const branches = useAtomValue(branchesState);
  const branch = useAtomValue(currentBranchAtom);
  const [, setBranchInQueryString] = useQueryParam(QSP.BRANCH, StringParam);

  const valueLabel = (
    <div className="flex items-center fill-custom-white">
      {getBranchIcon(branch, true)}

      <p className="ml-2.5 text-sm font-medium truncate">{branch?.name}</p>
    </div>
  );

  const branchesOptions: SelectOption[] = branchesToSelectOptions(branches);

  const onBranchChange = (branch: Branch) => {
    if (branch?.is_default) {
      // undefined is needed to remove a parameter from the QSP
      setBranchInQueryString(undefined);
    } else {
      setBranchInQueryString(branch.name);
    }
  };

  const renderOption = ({ option, active, selected }: any) => (
    <div className="flex relative flex-col">
      <div className="flex absolute bottom-0 right-0">{getBranchIcon(option, active)}</div>

      <div className="flex justify-between">
        <p className={selected ? "font-semibold" : "font-normal"}>{option.name}</p>
        {selected ? (
          <span className={active ? "text-custom-white" : "text-gray-500"}>
            <Icon icon={"mdi:check"} />
          </span>
        ) : null}
      </div>

      {option?.created_at && <DateDisplay date={option?.created_at} />}
    </div>
  );

  /**
   * There's always a main branch present at least.
   */
  if (!branches.length) {
    return null;
  }

  return (
    <div className="flex h-12 w-full" data-cy="branch-select-menu" data-testid="branch-select-menu">
      <SelectButton
        value={branch}
        valueLabel={valueLabel}
        onChange={onBranchChange}
        options={branchesOptions}
        renderOption={renderOption}
      />

      <BranchFormTrigger />
    </div>
  );
}

export const BranchFormTrigger = () => {
  const permission = usePermission();
  const [open, setOpen] = React.useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <ButtonWithTooltip
          disabled={!permission.write.allow}
          tooltipEnabled={!permission.write.allow}
          tooltipContent={permission.write.message ?? undefined}
          className="h-full shadow-none rounded-none rounded-r-md px-2.5"
          data-testid="create-branch-button">
          <Icon icon="mdi:plus" />
        </ButtonWithTooltip>
      </PopoverTrigger>

      <PopoverContent>
        <header className="font-semibold text-base text-center pb-2">Create a branch</header>
        <div className="border-b flex" />
        <BranchCreateForm onCancel={() => setOpen(false)} onSuccess={() => setOpen(false)} />
      </PopoverContent>
    </Popover>
  );
};
