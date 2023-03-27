import { CheckIcon } from "@heroicons/react/20/solid";
import { CircleStackIcon, PlusIcon, ShieldCheckIcon } from "@heroicons/react/24/outline";
import { format, formatDistanceToNow } from "date-fns";
import { useAtom } from "jotai";
import { useState } from "react";
import { graphQLClient } from "..";
import { CONFIG } from "../config/config";
import { Branch } from "../generated/graphql";
import { branchState } from "../state/atoms/branch.atom";
import { branchesState } from "../state/atoms/branches.atom";
import { timeState } from "../state/atoms/time.atom";
import { classNames } from "../utils/common";
import { Button, BUTTON_TYPES } from "./button";
import Enum from "./enum";
import { PopOver } from "./popover";
import { RoundedButton } from "./rounded-button";
import Select from "./select";

export default function BranchSelector() {
  const [branch, setBranch] = useAtom(branchState);
  const [branches] = useAtom(branchesState);

  const branchesOptions = branches.map(
    (branch) => ({
      name: branch.name 
    })
  );
  console.log("branchesOptions: ", branchesOptions);

  const [date] = useAtom(timeState);
  const [newBranchName, setNewBranchName] = useState("");
  const [branchedFrom, setBranchedFrom] = useState();
  console.log("branchedFrom: ", branchedFrom);
  const [branchedAt] = useState(new Date());

  /**
   * Update GraphQL client endpoint whenever branch changes
   */
  const onBranchChange = (branch: Branch) => {
    graphQLClient.setEndpoint(CONFIG.GRAPHQL_URL(branch?.name, date));
    setBranch(branch);
  };

  const valueLabel = (
    <>
      <CheckIcon className="h-5 w-5" aria-hidden="true" />
      <p className="ml-2.5 text-sm font-medium">
        {branch
          ? branch?.name
          : branches.filter((b) => b.name === "main")[0]?.name}
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

  const handleBranchedFrom = (newBranch: any) => setBranchedFrom(newBranch);

  const renderOption = ({ option, active, selected }: any) => (
    <div className="flex relative flex-col">
      {option.is_data_only && (
        <div className="absolute bottom-0 right-0">
          <CircleStackIcon
            className={classNames(
              "h-4 w-4",
              active ? "text-white" : "text-gray-500"
            )}
          />
        </div>
      )}

      {option.is_default && (
        <div className="absolute bottom-0 right-0">
          <ShieldCheckIcon
            className={classNames(
              "h-4 w-4",
              active ? "text-white" : "text-gray-500"
            )}
          />
        </div>
      )}

      <div className="flex justify-between">
        <p
          className={
            selected ? "font-semibold" : "font-normal"
          }
        >
          {option.name}
        </p>
        {selected ? (
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
        ) : null}
      </div>
      {option?.created_at && (
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
      )}
    </div>
  );

  const createBranch = () => {

  };

  /**
   * There's always a main branch present at least.
   */
  if (!branches.length) {
    return null;
  }

  console.log("branchedFrom ?? branchesOptions[0]?.name: ", branchedFrom ?? branchesOptions[0]?.name);

  return (
    <>
      <Select
        value={branch ? branch : branches.filter((b) => b.name === "main")[0]}
        valueLabel={valueLabel}
        onChange={onBranchChange}
        options={branches}
        renderOption={renderOption}
      />
      <PopOver buttonComponent={PopOverButton} className="right-0">
        Branch name:
        <input
          className="block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6 px-2"
          value={newBranchName}
          onChange={(e) => setNewBranchName(e.target.value)}
        />

        Branched from:
        <Enum disabled options={branchesOptions} value={branchedFrom ?? branchesOptions[0]?.name} onChange={handleBranchedFrom} />


        Branched at:
        <input
          className="block w-full rounded-md border-0 py-1.5 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 focus:ring-2 focus:ring-inset focus:ring-indigo-600 sm:text-sm sm:leading-6 px-2"
          value={format(branchedAt, "MM/dd/yyy HH:mm")}
          // onChange={(e) => setBranchedAt(e.target.value)}
          disabled
        />


        <Button type={BUTTON_TYPES.VALIDATE} onClick={createBranch} className="mt-2">Create</Button>
      </PopOver>
    </>
  );
}
