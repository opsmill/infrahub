import { useAtom } from "jotai";
import type React from "react";
import { useEffect } from "react";
import { Navigate, useLocation } from "react-router";

import { QSP } from "@/shared/config/qsp";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { ServicePortalHeader } from "@/entities/service-portal/ui/service-portal-header";

const NON_DEFAULT_BRANCH_QSP = [QSP.BRANCH, QSP.DATETIME];

// Every portal page works on the live default branch. Dropping the branch and time-travel params
// makes BranchesProvider, SchemaProvider and every shared form widget below resolve to it too.
export function ServicePortalLayout({ children }: { children?: React.ReactNode }) {
  const location = useLocation();
  const [datetime, setDatetime] = useAtom(datetimeAtom);

  useEffect(() => {
    if (datetime) setDatetime(null);
  }, [datetime]);

  const searchParams = new URLSearchParams(location.search);
  if (NON_DEFAULT_BRANCH_QSP.some((qsp) => searchParams.has(qsp))) {
    for (const qsp of NON_DEFAULT_BRANCH_QSP) searchParams.delete(qsp);
    return <Navigate to={{ ...location, search: searchParams.toString() }} replace />;
  }

  if (datetime) return null;

  return (
    <div className="flex h-screen w-screen flex-col gap-0.5 bg-stone-100 p-0.5 text-stone-800">
      <ServicePortalHeader />

      <main className="flex-1 overflow-auto">
        <div className="mx-auto max-w-5xl p-6">{children}</div>
      </main>
    </div>
  );
}
