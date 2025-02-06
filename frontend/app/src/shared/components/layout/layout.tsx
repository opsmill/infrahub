import { QSP } from "@/config/qsp";
import { branchesState } from "@/entities/branches/stores";
import { SchemaContext, withSchemaContext } from "@/entities/schema/decorators/withSchemaContext";
import Sidebar from "@/shared/components/layout/sidebar";
import { useAtomValue } from "jotai/index";
import { useContext, useEffect } from "react";
import { Outlet } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import Header from "./header";

function Layout() {
  const branches = useAtomValue(branchesState);
  const [branchInQueryString] = useQueryParam(QSP.BRANCH, StringParam);
  const { checkSchemaUpdate } = useContext(SchemaContext);

  useEffect(() => {
    if (branches.length === 0) return;
    checkSchemaUpdate();
  }, [branches.length, branchInQueryString]);

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
