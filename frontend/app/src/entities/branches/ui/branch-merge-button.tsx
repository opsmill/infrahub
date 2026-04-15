import { useMutation } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { toast } from "react-toastify";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Button } from "@/shared/components/ui/button";
import { datetimeAtom } from "@/shared/stores/time.atom";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { BRANCH_MERGE } from "@/entities/branches/api/mergeBranch";
import { BRANCH_STATUS } from "@/entities/branches/constants";
import type { BranchDetail } from "@/entities/branches/domain/branch.mappers";
import { useNavigateAfterBranchRemoval } from "@/entities/branches/ui/hooks/use-navigate-after-branch-removal";
import { useConfig } from "@/entities/config/ui/config-provider";

type BranchMergeButtonProps = {
  branch: BranchDetail;
};

export const BranchMergeButton = ({ branch }: BranchMergeButtonProps) => {
  const { isAuthenticated } = useAuth();
  const date = useAtomValue(datetimeAtom);
  const config = useConfig();
  const { navigateToPage } = useNavigateAfterBranchRemoval();

  const [merge, { loading: isPending }] = useMutation(BRANCH_MERGE, {
    client: graphqlClient,
    variables: { name: branch.name },
    context: { branch: branch.name, date },
    onCompleted: () => {
      const deleteBranchAfterMerge = config.main.delete_branch_after_merge;

      const message = deleteBranchAfterMerge
        ? `Branch merge requested! Branch '${branch.name}' will be automatically deleted.`
        : "Branch merge requested!";

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={message} />, {
        toastId: "alert-success",
      });

      if (deleteBranchAfterMerge) {
        navigateToPage("/branches", branch.name);
      }
    },
    onError: () => {
      toast(
        <Alert type={ALERT_TYPES.ERROR} message="An error occurred while merging the branch" />
      );
    },
  });

  const isDisabled =
    !isAuthenticated || !!branch.is_default || branch.status === BRANCH_STATUS.MERGED || isPending;

  return (
    <Button
      disabled={isDisabled}
      isLoading={isPending}
      onClick={() => merge()}
      variant="active"
      className="flex items-center gap-2"
    >
      Merge
      <Icon icon="mdi:check" />
    </Button>
  );
};
