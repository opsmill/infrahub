import { QSP } from "@/config/qsp";
import { SchemaContext, withSchemaContext } from "@/decorators/withSchemaContext";
import { findSelectedBranch } from "@/utils/branches";
import { Branch } from "@generated/graphql";
import { useSetAtom } from "jotai";
import { useAtomValue } from "jotai/index";
import { useContext, useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import graphqlClient from "../../graphql/graphqlClientApollo";
import GET_BRANCHES from "../../graphql/queries/branches/getBranches";
import { branchesState, currentBranchAtom } from "../../state/atoms/branches.atom";
import LoadingScreen from "../loading-screen/loading-screen";
import Header from "./header";
import { Sidebar } from "./sidebar";

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
