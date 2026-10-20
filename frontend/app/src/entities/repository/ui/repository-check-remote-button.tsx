import { Button, Tooltip } from "@infrahub/ui";
import { ArrowUpRightIcon, RadarIcon } from "lucide-react";
import { toast } from "react-toastify";

import { Row } from "@/shared/components/container";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Link } from "@/shared/components/ui/link";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type { PermissionDecision } from "@/entities/permission/domain/model/permission";
import { useCheckRemoteRefsMutation } from "@/entities/repository/ui/queries/check-remote-refs.mutation";
import { useGetRemoteCheckTask } from "@/entities/repository/ui/queries/get-remote-check-task.query";

export interface RepositoryRemoteCheck {
  objectKind: string;
  updatePermission: PermissionDecision;
}

export interface RepositoryCheckRemoteButtonProps extends RepositoryRemoteCheck {
  repositoryId: string;
}

export function RepositoryCheckRemoteButton({
  repositoryId,
  objectKind,
  updatePermission,
}: RepositoryCheckRemoteButtonProps) {
  const { currentBranch } = useCurrentBranch();
  const { mutate: checkRemoteRefs } = useCheckRemoteRefsMutation();
  const { isSubmitting, isOngoing, taskId } = useGetRemoteCheckTask({ repositoryId });
  const runningTaskId = isOngoing ? taskId : null;

  const startCheck = () =>
    checkRemoteRefs(
      { repositoryId, branchName: currentBranch.name },
      {
        onError: (error) => {
          toast(
            <Alert
              type={ALERT_TYPES.ERROR}
              message={`Error checking the remote: ${error.message}`}
            />
          );
        },
      }
    );

  return (
    <Row className="items-center gap-2">
      <Row role="status" className="items-center gap-1 text-foreground-muted text-sm">
        {runningTaskId && (
          <>
            Check running.
            <Link
              to={getObjectDetailsUrl(
                objectKind,
                repositoryId,
                undefined,
                `tasks/${runningTaskId}`
              )}
              className="inline-flex items-center gap-1 underline"
            >
              View task <ArrowUpRightIcon className="size-3.5" />
            </Link>
          </>
        )}
      </Row>
      <Tooltip message={updatePermission.isAllowed ? undefined : updatePermission.message}>
        <Button
          variant="outline"
          size="sm"
          isDisabled={updatePermission.isAllowed && runningTaskId !== null}
          isDisabledAndFocusable={!updatePermission.isAllowed}
          isPending={isSubmitting}
          onPress={startCheck}
        >
          <RadarIcon aria-hidden="true" />
          Check remote now
        </Button>
      </Tooltip>
    </Row>
  );
}
