import { useGetBranches } from "@/entities/branches/domain/get-branches.query";
import { constructPath } from "@/shared/api/rest/fetch";
import { DateDisplay } from "@/shared/components/display/date-display";
import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { InfrahubLoading } from "@/shared/components/loading/infrahub-loading";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { useTitle } from "@/shared/hooks/useTitle";
import { sortByName } from "@/shared/utils/common";
import { Icon } from "@iconify-icon/react";
import { useNavigate } from "react-router";

const BranchesItems = () => {
  const navigate = useNavigate();
  useTitle("Branches list");
  const { data: storedBranches, refetch, isPending, error, isRefetching } = useGetBranches();

  if (isPending) {
    return <InfrahubLoading>loading branches...</InfrahubLoading>;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const sortedBranches = sortByName(storedBranches.filter((b) => b.name !== "main"));
  const branches = [...storedBranches.filter((b) => b.name === "main"), ...sortedBranches];

  return (
    <Content.Card>
      <Content.CardTitle
        title="Branches"
        badgeContent={branches.length}
        isReloadLoading={isRefetching}
        reload={() => refetch()}
      />

      <ul
        className="grid gap-6 grid-cols-1 p-6"
        data-cy="branches-items"
        data-testid="branches-items"
      >
        {branches.map((branch) => (
          <li
            key={branch.name}
            className="col-span-1 rounded-lg border border-gray-200 cursor-pointer bg-gray-50 hover:bg-gray-100"
            onClick={() => navigate(constructPath(`/branches/${branch.name}`))}
          >
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
    </Content.Card>
  );
};

export default BranchesItems;
