import { QSP } from "@/config/qsp";
import { useGetBranches } from "@/entities/branches/domain/get-branches.query";
import { findSelectedBranch } from "@/entities/branches/utils";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { InfrahubLoading } from "@/shared/components/loading/infrahub-loading";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";

export const BranchesProvider = ({ children }: { children?: React.ReactNode }) => {
  const { data: branches, isPending, error } = useGetBranches();
  const [branchInQueryString] = useQueryParam(QSP.BRANCH, StringParam);
  const navigate = useNavigate();

  useEffect(() => {
    if (isPending || error) return;

    const selectedBranch = findSelectedBranch(branches, branchInQueryString);
    if (branchInQueryString && !selectedBranch) {
      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message={
            <div>
              Branch <b>{branchInQueryString}</b> not found, you have been redirected to the main
              branch.
            </div>
          }
        />
      );
      navigate("/");
    }
  }, [branches, branchInQueryString]);

  if (isPending) {
    return <InfrahubLoading>loading branches...</InfrahubLoading>;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  return children;
};
