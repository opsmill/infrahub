import { Button, Tooltip } from "@infrahub/ui";
import { ArrowUpRightIcon, RadarIcon } from "lucide-react";
import { toast } from "react-toastify";

import { constructPath } from "@/shared/api/rest/fetch";
import { Row } from "@/shared/components/container";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Link } from "@/shared/components/ui/link";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type { PermissionDecision } from "@/entities/permission/domain/model/permission";
import { useCheckRemoteRefsMutation } from "@/entities/repository/ui/queries/check-remote-refs.mutation";
import { useGetRemoteCheckTask } from "@/entities/repository/ui/queries/get-remote-check-task.query";

export interface RepositoryCheckRemoteButtonProps {
  repositoryId: string;
  updatePermission: PermissionDecision;
}

export function RepositoryCheckRemoteButton({
  repositoryId,
  updatePermission,
}: RepositoryCheckRemoteButtonProps) {
  const { currentBranch } = useCurrentBranch();
  const { isSubmitting, isOngoing, taskId } = useGetRemoteCheckTask({ repositoryId });

  const { mutate: checkRemoteRefs } = useCheckRemoteRefsMutation({
    onError: (error) => {
      toast(
        <Alert type={ALERT_TYPES.ERROR} message={`Error checking the remote: ${error.message}`} />
      );
    },
  });

  return (
    <Row className="ml-auto items-center gap-2">
      {isOngoing && taskId && (
        <Row className="items-center gap-1 text-foreground-muted text-sm">
          Check running.
          <Link
            to={constructPath(`/tasks/${taskId}`)}
            className="inline-flex items-center gap-1 underline"
          >
            View task <ArrowUpRightIcon className="size-3.5" />
          </Link>
        </Row>
      )}
      <Tooltip
        message={updatePermission.isAllowed ? undefined : updatePermission.message}
        nonInteractiveTrigger
      >
        <span>
          <Button
            variant="outline"
            size="sm"
            isDisabled={!updatePermission.isAllowed || isOngoing}
            isPending={isSubmitting}
            onPress={() => checkRemoteRefs({ repositoryId, branchName: currentBranch.name })}
          >
            <RadarIcon aria-hidden="true" />
            Check remote now
          </Button>
        </span>
      </Tooltip>
    </Row>
  );
}
