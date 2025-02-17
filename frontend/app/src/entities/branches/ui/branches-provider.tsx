import { DEFAULT_BRANCH_NAME } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { useGetBranches } from "@/entities/branches/domain/get-branches.query";
import { currentBranchAtom } from "@/entities/branches/stores";
import { findSelectedBranch } from "@/entities/branches/utils";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { InfrahubLoading } from "@/shared/components/loading/infrahub-loading";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { useAtom } from "jotai";
import React, { useEffect } from "react";
import { useNavigate } from "react-router";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";

export const BranchesProvider = ({ children }: { children?: React.ReactNode }) => {
  const { data: branches, isPending, error } = useGetBranches();
  const [currentBranch, setCurrentBranch] = useAtom(currentBranchAtom);
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
            <>
              Branch <b>{branchInQueryString}</b> not found, you have been redirected to the main
              branch.
            </>
          }
        />
      );
      const mainBranch = findSelectedBranch(branches, DEFAULT_BRANCH_NAME);
      setCurrentBranch(mainBranch);
      navigate("/");
    }

    setCurrentBranch(selectedBranch);
  }, [branches, branchInQueryString]);

  if (isPending || !currentBranch) {
    return <InfrahubLoading>loading branches...</InfrahubLoading>;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  return children;
};
