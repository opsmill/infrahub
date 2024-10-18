import { QSP } from "@/config/qsp";
import { SchemaContext, withSchemaContext } from "@/decorators/withSchemaContext";
import { Branch } from "@/generated/graphql";
import GET_BRANCHES from "@/graphql/queries/branches/getBranches";
import Sidebar from "@/screens/layout/sidebar";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { branchesState, currentBranchAtom } from "@/state/atoms/branches.atom";
import { findSelectedBranch } from "@/utils/branches";
import { NetworkStatus, useQuery } from "@apollo/client";
import { useSetAtom } from "jotai";
import { useAtomValue } from "jotai/index";
import { useContext, useEffect } from "react";
import { Outlet } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import Header from "./header";

function Layout() {
  const branches = useAtomValue(branchesState);
  const [branchInQueryString] = useQueryParam(QSP.BRANCH, StringParam);
  const { checkSchemaUpdate } = useContext(SchemaContext);
  const setBranches = useSetAtom(branchesState);
  const setCurrentBranch = useSetAtom(currentBranchAtom);
  const { networkStatus } = useQuery(GET_BRANCHES, {
    notifyOnNetworkStatusChange: true,
    onCompleted: (data) => {
      const branches: Branch[] = data.Branch ?? [];
      const selectedBranch = findSelectedBranch(branches, branchInQueryString);

      setBranches(branches);
      setCurrentBranch(selectedBranch);
    },
    onError: (err) => {
      console.error("err.message: ", err.message);

      if (err?.message?.includes("Received status code 401")) {
        return [];
      }

      console.error("Error while fetching branches: ", err);
    },
  });

  useEffect(() => {
    if (branches.length === 0) return;
    checkSchemaUpdate();
  }, [branches.length, branchInQueryString]);

  if (networkStatus === NetworkStatus.loading) {
    return (
      <div className="w-screen h-screen flex items-center justify-center">
        <LoadingScreen message="Loading branches..." />
      </div>
    );
  }

  return (
    <div className="h-screen w-screen overflow-hidden bg-stone-100 text-stone-800">
      <Header />

      <div className="flex items-stretch h-[calc(100vh-57px)]">
        <Sidebar />

        <main className="flex-grow overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export const Component = withSchemaContext(Layout);
