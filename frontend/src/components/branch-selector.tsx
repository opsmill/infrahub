import { CheckIcon } from "@heroicons/react/20/solid";
import { CircleStackIcon, PlusIcon, ShieldCheckIcon } from "@heroicons/react/24/outline";
import { formatDistanceToNow } from "date-fns";
import { useAtom } from "jotai";
import { graphQLClient } from "..";
import { CONFIG } from "../config/config";
import { Branch } from "../generated/graphql";
import { branchState } from "../state/atoms/branch.atom";
import { branchesState } from "../state/atoms/branches.atom";
import { timeState } from "../state/atoms/time.atom";
import { classNames } from "../utils/common";
import { RoundedButton } from "./rounded-button";
import Select from "./select";

export default function BranchSelector() {
  const [branch, setBranch] = useAtom(branchState);
  const [branches] = useAtom(branchesState);
  console.log("branches: ", branches);
  const [date] = useAtom(timeState);

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
  )

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
  )

  /**
   * There's always a main branch present at least.
   */
  if (!branches.length) {
    return null;
  }

  return (
    <>
      <Select
        value={branch ? branch : branches.filter((b) => b.name === "main")[0]}
        valueLabel={valueLabel}
        onChange={onBranchChange}
        options={branches}
        renderOption={renderOption}
      />
      <RoundedButton className="ml-2 bg-blue-500 text-sm hover:bg-blue-600 focus:ring-blue-500 focus:ring-offset-gray-50 focus:ring-offset-2">
        <PlusIcon
          className="h-5 w-5 text-white"
          aria-hidden="true"
        />
      </RoundedButton>
    </>
  );
}
