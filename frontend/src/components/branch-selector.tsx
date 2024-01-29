import { useMutation } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { formatDistanceToNow } from "date-fns";
import { useAtom } from "jotai";
import { useAtomValue } from "jotai/index";
import { useContext } from "react";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "../config/qsp";
import { AuthContext } from "../decorators/withAuth";
import { Branch } from "../generated/graphql";
import { BRANCH_CREATE } from "../graphql/mutations/branches/createBranch";
import { DynamicFieldData } from "../screens/edit-form-hook/dynamic-control-types";
import { Form } from "../screens/edit-form-hook/form";
import { branchesState, currentBranchAtom } from "../state/atoms/branches.atom";
import { classNames } from "../utils/common";
import { BUTTON_TYPES, Button } from "./buttons/button";
import { SelectButton } from "./buttons/select-button";
import { POPOVER_SIZE, PopOver } from "./display/popover";
import { SelectOption } from "./inputs/select";

export default function BranchSelector() {
  const [branches, setBranches] = useAtom(branchesState);
  const [, setBranchInQueryString] = useQueryParam(QSP.BRANCH, StringParam);
  const branch = useAtomValue(currentBranchAtom);
  const auth = useContext(AuthContext);

  const [createBranch, { loading }] = useMutation(BRANCH_CREATE);

  const valueLabel = (
    <>
      <Icon icon={"mdi:layers-triple"} />
      <p className="ml-2.5 text-sm font-medium truncate">{branch?.name}</p>
    </>
  );

  const PopOverButton = (
    <Button
      disabled={!auth?.permissions?.write}
      buttonType={BUTTON_TYPES.MAIN}
      className="h-full rounded-r-md border border-transparent"
      type="submit"
      data-cy="create-branch-button"
      data-testid="create-branch-button">
      <Icon icon={"mdi:plus"} className="text-custom-white" />
    </Button>
  );

  const branchesOptions: SelectOption[] = branches
    .map((branch) => ({
      id: branch.id,
      name: branch.name,
      is_data_only: branch.is_data_only,
      is_default: branch.is_default,
      created_at: branch.created_at,
    }))
    .sort((branch1, branch2) => {
      if (branch1.name === "main") {
        return -1;
      }

      if (branch2.name === "main") {
        return 1;
      }

      if (branch2.name === "main") {
        return -1;
      }

      if (branch1.name > branch2.name) {
        return 1;
      }

      return -1;
    });

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
      {option.is_data_only && (
        <div className="absolute bottom-0 right-0">
          <Icon
            icon={"mdi:database"}
            className={classNames(active ? "text-custom-white" : "text-gray-500")}
          />
        </div>
      )}

      {option.is_default && (
        <div className="absolute bottom-0 right-0">
          <Icon
            icon={"mdi:shield-check"}
            className={classNames(active ? "text-custom-white" : "text-gray-500")}
          />
        </div>
      )}

      <div className="flex justify-between">
        <p className={selected ? "font-semibold" : "font-normal"}>{option.name}</p>
        {selected ? (
          <span className={active ? "text-custom-white" : "text-gray-500"}>
            <Icon icon={"mdi:check"} />
          </span>
        ) : null}
      </div>

      {option?.created_at && (
        <p className={classNames(active ? "text-custom-white" : "text-gray-500", "mt-2")}>
          {formatDistanceToNow(new Date(option?.created_at), {
            addSuffix: true,
          })}
        </p>
      )}
    </div>
  );

  const handleSubmit = async (data: any, close: Function) => {
    const { name, description, is_data_only } = data;

    try {
      const { data: response } = await createBranch({
        variables: {
          name,
          description,
          is_data_only,
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
      options: {
        values: branchesOptions,
      },
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
      name: "is_data_only",
      label: "Data only",
      type: "checkbox",
      value: true,
      isOptional: true,
    },
  ];

  return (
    <div className="flex" data-cy="branch-select-menu" data-testid="branch-select-menu">
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
