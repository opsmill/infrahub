import { DateDisplay } from "@/components/display/date-display";
import { Badge } from "@/components/ui/badge";
import { Tooltip } from "@/components/ui/tooltip";
import GET_BRANCHES from "@/graphql/queries/branches/getBranches";
import { useLazyQuery } from "@/hooks/useQuery";
import { useTitle } from "@/hooks/useTitle";
import { branchesState } from "@/state/state/atoms/branches.atom";
import { constructPath } from "@/utils/fetch";
import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import * as R from "ramda";
import { useNavigate } from "react-router-dom";
import Content from "../layout/content";

const BranchesItems = () => {
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
      <Content.Title
        title={
          <div className="flex items-center">
            <h1 className="mr-2 truncate">Branches</h1>
            <Badge>{branches.length}</Badge>
          </div>
        }
        isReloadLoading={loading}
        reload={handleRefresh}
      />

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
                  <div className="flex flex-1 items-center">
                    <div className="flex items-center">
                      {branch.is_default && (
                        <Tooltip enabled content={"Default branch"}>
                          <Icon icon={"mdi:shield-star"} className="text-gray-400 mr-1" />
                        </Tooltip>
                      )}

                      {branch.sync_with_git && (
                        <Tooltip enabled content={"Sync with Git"}>
                          <Icon icon={"mdi:git"} className="text-red-400 mr-1" />
                        </Tooltip>
                      )}

                      {branch.has_schema_changes && (
                        <Tooltip enabled content={"Has schema changes"}>
                          <Icon icon={"mdi:file-alert"} className="text-gray-400 mr-1" />
                        </Tooltip>
                      )}
                    </div>

                    <div className="text-base font-semibold leading-6 text-gray-900">
                      {branch.name}
                    </div>
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

export default BranchesItems;
