import { Outlet } from "react-router-dom";
import Header from "./header";
import { Sidebar } from "./sidebar";
import { useAtomValue } from "jotai/index";
import { branchesState, currentBranchAtom } from "../../state/atoms/branches.atom";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "../../config/qsp";
import { useContext, useEffect, useState } from "react";
import { SchemaContext, withSchemaContext } from "../../decorators/withSchemaContext";
import GET_BRANCHES from "../../graphql/queries/branches/getBranches";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { useSetAtom } from "jotai";
import { Branch } from "../../generated/graphql";
import { findSelectedBranch } from "../../utils/branches";
import LoadingScreen from "../loading-screen/loading-screen";

function Layout() {
  const branches = useAtomValue(branchesState);
  const [branchInQueryString] = useQueryParam(QSP.BRANCH, StringParam);
  const { checkSchemaUpdate } = useContext(SchemaContext);
  const setBranches = useSetAtom(branchesState);
  const setCurrentBranch = useSetAtom(currentBranchAtom);
  const [isLoadingBranches, setIsLoadingBranches] = useState(true);

  const fetchBranches = async () => {
    try {
      const { data }: any = await graphqlClient.query({
        query: GET_BRANCHES,
        context: { branch: branchInQueryString },
      });

      return data.Branch ?? [];
    } catch (err: any) {
      console.error("err.message: ", err.message);

      if (err?.message?.includes("Received status code 401")) {
        return [];
      }

      console.error("Error while fetching branches: ", err);

      return [];
    }
  };

  /**
   * Set branches in state atom
   */
  const setBranchesInState = async () => {
    const branches: Branch[] = await fetchBranches();

    const selectedBranch = findSelectedBranch(branches, branchInQueryString);

    setBranches(branches);
    setCurrentBranch(selectedBranch);
    setIsLoadingBranches(false);
  };

  useEffect(() => {
    setBranchesInState();
  }, []);

  useEffect(() => {
    if (branches.length === 0) return;
    checkSchemaUpdate();
  }, [branches.length, branchInQueryString]);

  if (isLoadingBranches) {
    return (
      <div className="w-screen h-screen flex">
        <LoadingScreen />;
      </div>
    );
  }
  return (
    <div className="h-screen flex">
      <Sidebar />

      <div className="flex flex-1 flex-col bg-gray-100 overflow-hidden">
        <Header />

        <Outlet />
      </div>
    </div>
  );
}

export default withSchemaContext(Layout);
