import { CheckIcon } from "@heroicons/react/20/solid";
import { CircleStackIcon, PlusIcon, ShieldCheckIcon } from "@heroicons/react/24/outline";
import { format, formatDistanceToNow } from "date-fns";
import { useAtom } from "jotai";
import { useCallback, useState } from "react";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";
import { graphQLClient } from "..";
import { CONFIG } from "../config/config";
import { Branch } from "../generated/graphql";
import createBranch from "../graphql/mutations/branches/createBranch";
import { branchState } from "../state/atoms/branch.atom";
import { branchesState } from "../state/atoms/branches.atom";
import { classNames } from "../utils/common";
import { Alert, ALERT_TYPES } from "./alert";
import { Button, BUTTON_TYPES } from "./button";
import { Input } from "./input";
import { PopOver } from "./popover";
import { RoundedButton } from "./rounded-button";
import { Select } from "./select";
import { SelectButton } from "./select-button";
import { Switch } from "./switch";

export default function BranchSelector() {
  const [branch, setBranch] = useAtom(branchState);
  const [branches] = useAtom(branchesState);
  const [branchInQueryString, setBranchInQueryString] = useQueryParam(CONFIG.QSP_BRANCH, StringParam);

  const [newBranchName, setNewBranchName] = useState("");
  const [newBranchDescription, setNewBranchDescription] = useState("");
  const [originBranch, setOriginBranch] = useState();
  const [branchedFrom] = useState(); // TODO: Add camendar component
  const [isDataOnly, setIsDataOnly] = useState(true);

  const getCurrentBranch = useCallback(() :Branch => {
    if(branch) {
      return branch;
    }

    if(branchInQueryString) {
      return branches.filter((b) => b.name === branchInQueryString.trim())[0];
    } else {
      return branches.filter(b => b.is_default)[0];
    }
  }, [branch, branchInQueryString, branches]);

  const valueLabel = (
    <>
      <CheckIcon className="h-5 w-5" aria-hidden="true" />
      <p className="ml-2.5 text-sm font-medium">
        {
          getCurrentBranch()?.name
        }
      </p>
    </>
  );

  const PopOverButton = (
    <RoundedButton className="ml-2 bg-blue-500 text-sm hover:bg-blue-600 focus:ring-blue-500 focus:ring-offset-gray-50 focus:ring-offset-2">
      <PlusIcon
        className="h-5 w-5 text-white"
        aria-hidden="true"
      />
    </RoundedButton>
  );

  const branchesOptions = branches.map(
    (branch) => ({
      name: branch.name
    })
  );

  const defaultBranch = branches?.filter(b => b.is_default)[0]?.name;

  /**
   * Update GraphQL client endpoint whenever branch changes
   */
  const onBranchChange = useCallback((branch: Branch) => {
    if(branch) {
      graphQLClient.setEndpoint(CONFIG.GRAPHQL_URL(branch.name));
    }

    setBranch(branch);

    if (branch?.is_default) {
      // undefined is needed to remove a parameter from the QSP
      setBranchInQueryString(undefined);
    } else {
      setBranchInQueryString(branch.name);
    }
  }, [setBranch, setBranchInQueryString]);

  const handleBranchedFrom = (newBranch: any) => setOriginBranch(newBranch);

  const renderOption = ({ option, active, selected }: any) => (
    <div className="flex relative flex-col">
      {
        option.is_data_only
        && (
          <div className="absolute bottom-0 right-0">
            <CircleStackIcon
              className={classNames(
                "h-4 w-4",
                active ? "text-white" : "text-gray-500"
              )}
            />
          </div>
        )
      }

      {
        option.is_default
        && (
          <div className="absolute bottom-0 right-0">
            <ShieldCheckIcon
              className={classNames(
                "h-4 w-4",
                active ? "text-white" : "text-gray-500"
              )}
            />
          </div>
        )
      }

      <div className="flex justify-between">
        <p
          className={
            selected ? "font-semibold" : "font-normal"
          }
        >
          {option.name}
        </p>
        {
          selected
            ? (
              <span
                className={
                  active ? "text-white" : "text-blue-500"
                }
              >
                <CheckIcon
                  className="h-5 w-5"
                  aria-hidden="true"
                />
              </span>
            )
            : null
        }
      </div>
      {
        option?.created_at
        && (
          <p
            className={classNames(
              active ? "text-blue-200" : "text-gray-500",
              "mt-2"
            )}
          >
            {formatDistanceToNow(
              new Date(option?.created_at),
              { addSuffix: true }
            )}
          </p>
        )
      }
    </div>
  );

  const handleSubmit = async () => {
    try {
      await createBranch({
        name: newBranchName,
        description: newBranchDescription,
        // origin_branch: originBranch ?? branches[0]?.name,
        // branched_from: formatISO(branchedFrom ?? new Date()),
        is_data_only: isDataOnly
      });

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Branch created"} />);
    } catch (e) {
      const details = "An error occured while creating the branch";
      toast(<Alert type={ALERT_TYPES.ERROR} message={"An error occured"} details={details} />);
    }
  };

  /**
   * There's always a main branch present at least.
   */
  if (!branches.length) {
    return null;
  }

  return (
    <>
      <SelectButton
        value={getCurrentBranch()}
        valueLabel={valueLabel}
        onChange={onBranchChange}
        options={branches}
        renderOption={renderOption}
      />
      <PopOver buttonComponent={PopOverButton} className="right-0" title={"Create a new branch"}>
        <div className="flex flex-col">
          Branch name:
          <Input value={newBranchName} onChange={setNewBranchName} />

          Branch description:
          <Input value={newBranchDescription} onChange={setNewBranchDescription} />

          Branched from:
          <Select disabled options={branchesOptions} value={originBranch ?? defaultBranch} onChange={handleBranchedFrom} />

          Branched at:
          <Input value={format(branchedFrom ?? new Date(), "MM/dd/yyy HH:mm")} onChange={setNewBranchName} disabled />

          Is data only:
          <Switch enabled={isDataOnly} onChange={setIsDataOnly} />
        </div>

        <div className="flex justify-center">
          <Button type={BUTTON_TYPES.VALIDATE} onClick={handleSubmit} className="mt-2">Create</Button>
        </div>
      </PopOver>
    </>
  );
}
