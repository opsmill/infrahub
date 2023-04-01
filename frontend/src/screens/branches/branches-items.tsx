import { ShieldCheckIcon } from "@heroicons/react/24/outline";
import { formatDistanceToNow } from "date-fns";
import { useAtom } from "jotai";
import * as R from "ramda";
import { useNavigate } from "react-router-dom";
import { Badge } from "../../components/badge";
import { Pill } from "../../components/pill";
import { Tooltip } from "../../components/tooltip";
import { branchesState } from "../../state/atoms/branches.atom";

export const BranchesItems = () => {
  const [storedBranches] = useAtom(branchesState);
  const navigate = useNavigate();

  const sortByName = R.sortBy(R.compose(R.toLower, R.prop("name")));

  const sortedBranches = sortByName(storedBranches.filter(b => b.name !== "main"));

  const branches = [
    ...storedBranches.filter(b => b.name === "main"),
    ...sortedBranches
  ];

  return (
    <ul className="grid gap-6 grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 p-6">
      {
        branches.map(
          (branch) => (
            <li
              className="col-span-1 rounded-lg bg-white shadow cursor-pointer hover:bg-gray-50"
              key={branch.name}
              onClick={() => navigate(`/branches/${branch.id}`)}
            >
              <div className="flex w-full items-center justify-between space-x-6 p-6">
                <div className="flex flex-1">
                  <div className="flex flex-1 flex-col">
                    <div className="flex flex-1 items-center space-x-3">
                      {
                        branch.is_default
                          && (
                            <Tooltip message={"Default branch"}>
                              <ShieldCheckIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
                            </Tooltip>
                          )
                      }

                      <h3 className="text-sm font-medium text-gray-900 py-0.5">{branch.test.nothing}</h3>

                      {
                        !branch.is_default
                          && (
                            <Tooltip message={"Origin branch"}>
                              <Badge>{branch.origin_branch}</Badge>
                            </Tooltip>
                          )
                      }
                    </div>

                    <p className="mt-2 text-sm text-gray-500">
                      {branch.description || "-"}
                    </p>
                  </div>

                  <div className="flex flex-col items-end">
                    <Pill>Branched {formatDistanceToNow(new Date(branch.branched_from), { addSuffix: true })}</Pill>

                    {
                      !branch.is_default
                        && (
                          <Pill className="mt-2">Created {formatDistanceToNow(new Date(branch.created_at), { addSuffix: true })}</Pill>
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
  );
};