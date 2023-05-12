import { ChevronLeftIcon, ShieldCheckIcon } from "@heroicons/react/24/outline";
import { formatDistanceToNow } from "date-fns";
import { useAtom } from "jotai";
import * as R from "ramda";
import { useNavigate } from "react-router-dom";
import { Badge } from "../../components/badge";
import { DateDisplay } from "../../components/date-display";
import { Pill } from "../../components/pill";
import { Tooltip } from "../../components/tooltip";
import { branchesState } from "../../state/atoms/branches.atom";
import { constructPath } from "../../utils/fetch";

export const BranchesItems = () => {
  const [storedBranches] = useAtom(branchesState);
  const navigate = useNavigate();

  const sortByName = R.sortBy(R.compose(R.toLower, R.prop("name")));

  const sortedBranches = sortByName(storedBranches.filter((b) => b.name !== "main"));

  const branches = [...storedBranches.filter((b) => b.name === "main"), ...sortedBranches];

  return (
    <ul className="grid gap-6 grid-cols-1 p-6">
      {branches.map((branch) => (
        <li
          className="col-span-1 rounded-lg bg-white shadow cursor-pointer hover:bg-gray-50"
          key={branch.name}
          onClick={() => navigate(constructPath(`/branches/${branch.name}`))}>
          <div className="flex w-full items-center justify-between space-x-6 p-6">
            <div className="flex flex-1">
              <div className="flex flex-1 flex-col">
                <div className="flex flex-1 items-center space-x-3">
                  {branch.is_default && (
                    <>
                      <Tooltip message={"Default branch"}>
                        <ShieldCheckIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
                      </Tooltip>

                      <div className="text-base font-semibold leading-6 text-gray-900">
                        {branch.name}
                      </div>
                    </>
                  )}

                  {!branch.is_default && (
                    <div className="flex items-center">
                      <Tooltip message={"Destination branch"}>
                        <p className="max-w-2xl text-sm text-gray-500">main</p>
                      </Tooltip>

                      <ChevronLeftIcon
                        className="h-5 w-5 mx-2 flex-shrink-0 text-gray-400"
                        aria-hidden="true"
                      />

                      <div className="text-base font-semibold leading-6 text-gray-900 mr-2">
                        {branch.name}
                      </div>

                      <Tooltip message={"Origin branch"}>
                        <Badge>{branch.origin_branch}</Badge>
                      </Tooltip>
                    </div>
                  )}
                </div>

                <p className="mt-2 text-sm text-gray-500">{branch.description || "-"}</p>
              </div>

              <div className="flex flex-col items-end">
                <Tooltip message={<DateDisplay date={branch.branched_from} />}>
                  <Pill>
                    Branched{" "}
                    {formatDistanceToNow(new Date(branch.branched_from), { addSuffix: true })}
                  </Pill>
                </Tooltip>

                {!branch.is_default && (
                  <Tooltip message={<DateDisplay date={branch.created_at} />}>
                    <Pill className="mt-2">
                      Created{" "}
                      {formatDistanceToNow(new Date(branch.created_at), { addSuffix: true })}
                    </Pill>
                  </Tooltip>
                )}
              </div>
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
};
