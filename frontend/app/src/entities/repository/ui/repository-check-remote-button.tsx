import { Button, Tooltip } from "@infrahub/ui";
import { ArrowUpRightIcon, RadarIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "react-toastify";

import { constructPath } from "@/shared/api/rest/fetch";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Link } from "@/shared/components/ui/link";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import type { PermissionDecision } from "@/entities/permission/domain/model/permission";
import { useCheckRemoteRefsMutation } from "@/entities/repository/ui/queries/check-remote-refs.mutation";
import { useRemoteCheckTask } from "@/entities/repository/ui/queries/remote-check-task.query";

export interface RepositoryCheckRemoteButtonProps {
  repositoryId: string;
  updatePermission: PermissionDecision;
}

interface StartedCheck {
  taskId: string;
  repositoryId: string;
  branchName: string;
}

export function RepositoryCheckRemoteButton({
  repositoryId,
  updatePermission,
}: RepositoryCheckRemoteButtonProps) {
  const { currentBranch } = useCurrentBranch();
  const [startedCheck, setStartedCheck] = useState<StartedCheck | null>(null);
  const taskId =
    startedCheck?.repositoryId === repositoryId && startedCheck.branchName === currentBranch.name
      ? startedCheck.taskId
      : null;
  const { isOngoing } = useRemoteCheckTask({ repositoryId, taskId });

  const { mutate: checkRemoteRefs, isPending } = useCheckRemoteRefsMutation({
    onSuccess: (result) => {
      if (result.taskId) {
        setStartedCheck({ taskId: result.taskId, repositoryId, branchName: currentBranch.name });
      }
    },
    onError: (error) => {
      toast(
        <Alert type={ALERT_TYPES.ERROR} message={`Error checking the remote: ${error.message}`} />
      );
    },
  });

  return (
    <div className="ml-auto flex items-center gap-2">
      {isOngoing && taskId && (
        <p className="flex items-center gap-1 text-foreground-muted text-sm">
          Check running.
          <Link
            to={constructPath(`/tasks/${taskId}`)}
            className="inline-flex items-center gap-1 underline"
          >
            View task <ArrowUpRightIcon className="size-3.5" />
          </Link>
        </p>
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
            isPending={isPending}
            onPress={() => checkRemoteRefs({ repositoryId })}
          >
            <RadarIcon aria-hidden="true" />
            Check remote now
          </Button>
        </span>
      </Tooltip>
    </div>
  );
}
