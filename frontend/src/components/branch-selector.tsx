import { useMutation } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { useAtomValue } from "jotai/index";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "../config/qsp";
import { Branch } from "../generated/graphql";
import { BRANCH_CREATE } from "../graphql/mutations/branches/createBranch";
import { useAuth } from "../hooks/useAuth";
import { usePermission } from "../hooks/usePermission";
import { DynamicFieldData } from "../screens/edit-form-hook/dynamic-control-types";
import { Form } from "../screens/edit-form-hook/form";
import { branchesState, currentBranchAtom } from "../state/atoms/branches.atom";
import { classNames } from "../utils/common";
import { BUTTON_TYPES } from "./buttons/button";
import { ButtonWithTooltip } from "./buttons/button-with-tooltip";
import { SelectButton } from "./buttons/select-button";
import { DateDisplay } from "./display/date-display";
import { POPOVER_SIZE, PopOver } from "./display/popover";
import { SelectOption } from "./inputs/select";
import { branchesToSelectOptions } from "../utils/branches";

const getBranchIcon = (branch: Branch | null, active?: Boolean) =>
  branch && (
    <>
      {branch.is_isolated && (
        <Icon
          icon={"mdi:alpha-i-box"}
          className={classNames(active ? "text-custom-white" : "text-gray-500")}
        />
      )}

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
  const [branches, setBranches] = useAtom(branchesState);
  const [, setBranchInQueryString] = useQueryParam(QSP.BRANCH, StringParam);
  const branch = useAtomValue(currentBranchAtom);
  const auth = useAuth();
  const permission = usePermission();

  const [createBranch, { loading }] = useMutation(BRANCH_CREATE);

  const valueLabel = (
    <div className="flex items-center fill-custom-white">
      {getBranchIcon(branch, true)}

      <p className="ml-2.5 text-sm font-medium truncate">{branch?.name}</p>
    </div>
  );

  const PopOverButton = (
    <ButtonWithTooltip
      disabled={!permission.write.allow}
      tooltipEnabled={!permission.write.allow}
      tooltipContent={permission.write.message ?? undefined}
      buttonType={BUTTON_TYPES.MAIN}
      className="h-full rounded-r-md border border-transparent"
      type="submit"
      data-cy="create-branch-button"
      data-testid="create-branch-button">
      <Icon icon={"mdi:plus"} className="text-custom-white" />
    </ButtonWithTooltip>
  );

  const branchesOptions: SelectOption[] = branchesToSelectOptions(branches);

  const defaultBranch = branches?.filter((b) => b.is_default)[0]?.id;

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

  const handleSubmit = async (data: any, close: Function) => {
    try {
      const { data: response } = await createBranch({
        variables: {
          ...data,
        },
      });

      const branchCreated = response?.BranchCreate?.object;

      if (branchCreated) {
        setBranches([...branches, branchCreated]);
        onBranchChange(branchCreated);
      }
      close();
    } catch (error) {
      console.error("Error while creating the branch: ", error);
    }
  };

  /**
   * There's always a main branch present at least.
   */
  if (!branches.length) {
    return null;
  }

  const fields: DynamicFieldData[] = [
    {
      name: "name",
      label: "New branch name",
      placeholder: "New branch",
      type: "text",
      value: "",
      config: {
        required: "Required",
      },
    },
    {
      name: "description",
      label: "New branch description",
      placeholder: "Description",
      type: "text",
      value: "",
      isOptional: true,
    },
    {
      name: "from",
      label: "Branched from",
      type: "select",
      value: defaultBranch,
      options: branchesOptions,
      isProtected: true,
      isOptional: true,
    },
    {
      name: "at",
      label: "Branched at",
      type: "datepicker",
      value: new Date(),
      isProtected: true,
      isOptional: true,
    },
    {
      name: "sync_with_git",
      label: "Sync with Git",
      type: "checkbox",
      value: false,
      isOptional: true,
    },
    {
      name: "is_isolated",
      label: "Isolated mode",
      type: "checkbox",
      value: false,
      isOptional: true,
    },
  ];

  return (
    <div className="flex h-12" data-cy="branch-select-menu" data-testid="branch-select-menu">
      <SelectButton
        value={branch}
        valueLabel={valueLabel}
        onChange={onBranchChange}
        options={branchesOptions}
        renderOption={renderOption}
      />
      <PopOver
        disabled={!auth?.permissions?.write}
        buttonComponent={PopOverButton}
        title={"Create a new branch"}
        width={POPOVER_SIZE.SMALL}>
        {({ close }: any) => (
          <Form
            onSubmit={(data) => handleSubmit(data, close)}
            fields={fields}
            submitLabel="Create branch"
            isLoading={loading}
            onCancel={close}
            resetAfterSubmit
          />
        )}
      </PopOver>
    </div>
  );
}
