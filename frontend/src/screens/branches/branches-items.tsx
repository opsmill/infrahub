import { ChevronLeftIcon, ShieldCheckIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import * as R from "ramda";
import { useNavigate } from "react-router-dom";
import { Retry } from "../../components/buttons/retry";
import { Badge } from "../../components/display/badge";
import { DateDisplay } from "../../components/display/date-display";
import { Tooltip } from "../../components/utils/tooltip";
import GET_BRANCHES from "../../graphql/queries/branches/getBranches";
import { useLazyQuery } from "../../hooks/useQuery";
import { useTitle } from "../../hooks/useTitle";
import { branchesState } from "../../state/atoms/branches.atom";
import { constructPath } from "../../utils/fetch";
import Content from "../layout/content";

export const BranchesItems = () => {
  const [storedBranches, setBranches] = useAtom(branchesState);
  const navigate = useNavigate();
  useTitle("Branches list");

  // TODO: refactor with index query
  const [fetchBranches, { loading }] = useLazyQuery(GET_BRANCHES);

  const sortByName = R.sortBy(R.compose(R.toLower, R.prop("name")));

  const sortedBranches = sortByName(storedBranches.filter((b) => b.name !== "main"));

  const branches = [...storedBranches.filter((b) => b.name === "main"), ...sortedBranches];

  const handleRefresh = async () => {
    const { data } = await fetchBranches();
    setBranches(data?.Branch ?? []);
  };

  return (
    <Content>
      <div className="flex items-center p-4 bg-custom-white">
        <h1 className="text-base font-semibold">Branches ({branches?.length})</h1>

        <div className="ml-2">
          <Retry isLoading={loading} onClick={handleRefresh} />
        </div>
      </div>

      <ul
        className="grid gap-6 grid-cols-1 p-6"
        data-cy="branches-items"
        data-testid="branches-items">
        {branches.map((branch) => (
          <li
            className="col-span-1 rounded-lg bg-custom-white shadow cursor-pointer hover:bg-gray-50"
            key={branch.name}
            onClick={() => navigate(constructPath(`/branches/${branch.name}`))}>
            <div className="flex w-full items-center justify-between space-x-6 p-6">
              <div className="flex flex-1">
                <div className="flex flex-1 flex-col">
                  <div className="flex flex-1 items-center space-x-3">
                    {branch.is_default && (
                      <>
                        <Tooltip message={"Default branch"}>
                          <ShieldCheckIcon className="ml-2 h-4 w-4" aria-hidden="true" />
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
                          className="w-4 h-4 mx-2 flex-shrink-0 text-gray-400"
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
                  <div className="flex items-center">
                    <div className="mr-2">Branched:</div>
                    <DateDisplay date={branch.branched_from} />
                  </div>

                  {!branch.is_default && (
                    <div className="flex items-center">
                      <div className="mr-2">Created:</div>
                      <DateDisplay date={branch.created_at} />
                    </div>
                  )}
                </div>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </Content>
  );
};
