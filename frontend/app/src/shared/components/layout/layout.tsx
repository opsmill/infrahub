import { QSP } from "@/config/qsp";
import { branchesState } from "@/entities/branches/stores";
import { SchemaContext, withSchemaContext } from "@/entities/schema/decorators/withSchemaContext";
import Sidebar from "@/shared/components/layout/sidebar";
import { useAtomValue } from "jotai/index";
import { use, useEffect } from "react";
import { Outlet } from "react-router";
import { StringParam, useQueryParam } from "use-query-params";
import Header from "./header";

function Layout() {
  const branches = useAtomValue(branchesState);
  const [branchInQueryString] = useQueryParam(QSP.BRANCH, StringParam);
  const { checkSchemaUpdate } = use(SchemaContext);

  useEffect(() => {
    if (branches.length === 0) return;
    checkSchemaUpdate();
  }, [branches.length, branchInQueryString]);

  return (
    <div className="h-screen w-screen  text-stone-800 p-px bg-stone-100">
      <div className="h-full w-full flex gap-px">
        <Sidebar />

        <div className="flex flex-col gap-px h-full grow overflow-hidden">
          <Header />

          <Outlet />
        </div>
      </div>
    </div>
  );
}

export const Component = withSchemaContext(Layout);
