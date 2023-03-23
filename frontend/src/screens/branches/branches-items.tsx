import { ArrowRightIcon, CheckIcon, ShieldCheckIcon } from "@heroicons/react/24/outline";
import { formatDistanceToNow } from "date-fns";
import { useAtom } from "jotai";
import * as R from "ramda";
import { Badge } from "../../components/badge";
import { Button, BUTTON_TYPES } from "../../components/button";
import { Pill } from "../../components/pill";
import { branchesState } from "../../state/atoms/branches.atom";

export const BranchesItems = () => {
  const [storedBranches] = useAtom(branchesState);

  const sortByName = R.sortBy(R.compose(R.toLower, R.prop("name")));

  const sortedBranches = sortByName(storedBranches.filter(b => b.name !== "main"));

  const branches = [
    ...storedBranches.filter(b => b.name === "main"),
    ...sortedBranches
  ]

  const mergeBranch = (id: string) => {
    console.log("id: ", id);
  }

  const rebaseBranch = (id: string) => {
    console.log("id: ", id);
  }

  const validateBranch = (id: string) => {
    console.log("id: ", id);
  }

  const createPulRequest = (id: string) => {
    console.log("id: ", id);
  }

  console.log("branches: ", branches);

  return (
    <ul className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 p-6">
      {
        branches.map(
          (branch) => (
            <li key={branch.name} className="col-span-1 divide-y divide-gray-200 rounded-lg bg-white shadow">
              <div className="flex w-full items-center justify-between space-x-6 p-6">
                <div className="flex-1 truncate">
                  <div className="flex items-center space-x-3">
                    {
                      branch.is_default
                      && (
                        <ShieldCheckIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
                      )
                    }

                    <h3 className="truncate text-sm font-medium text-gray-900">{branch.name}</h3>
                    {
                      !branch.is_default
                      && (
                        <Badge>{branch.origin_branch}</Badge>
                      )
                    }

                    <Pill>{formatDistanceToNow(new Date(branch.branched_from), { addSuffix: true })}</Pill>

                    {
                      !branch.is_default
                      && (
                        <>
                          <ArrowRightIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
                          <Pill>{formatDistanceToNow(new Date(branch.created_at), { addSuffix: true })}</Pill>
                        </>
                      )
                    }
                  </div>

                  <p className="mt-1 truncate text-sm text-gray-500">
                    {branch.description || "-"}
                  </p>
                </div>
              </div>
              <div>
                <div className="-mt-px px-3 py-3 flex divide-x divide-gray-200">
                  <div className="flex w-0 flex-1">
                    {
                      !branch.is_default
                      && (
                        <>
                          <Button
                            className="mr-3"
                            onClick={() => mergeBranch(branch.id)}
                            type={BUTTON_TYPES.VALIDATE}
                            disabled
                          >
                            Merge
                            <CheckIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
                          </Button>

                          <Button
                            className="mr-3"
                            onClick={() => createPulRequest(branch.id)}
                            disabled
                          >
                            Pull request
                            <CheckIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
                          </Button>

                          <Button
                            className="mr-3"
                            onClick={() => rebaseBranch(branch.id)}
                            disabled
                          >
                            Rebase
                            <CheckIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
                          </Button>

                          <Button
                            className="mr-3"
                            onClick={() => validateBranch(branch.id)}
                            type={BUTTON_TYPES.WARNING}
                          >
                            Validate
                            <ShieldCheckIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
                          </Button>

                          <Button
                            className="mr-3"
                            onClick={() => validateBranch(branch.id)}
                            type={BUTTON_TYPES.CANCEL}
                            disabled
                          >
                            Delete
                            <ShieldCheckIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
                          </Button>
                        </>
                      )
                    }
                  </div>
                </div>
              </div>
            </li>
          )
        )
      }
    </ul>
  )
}