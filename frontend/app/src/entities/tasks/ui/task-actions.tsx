import { Icon } from "@iconify-icon/react";
import { Button } from "@infrahub/ui";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowUpRightIcon } from "lucide-react";
import { useState } from "react";
import { useLocation } from "react-router";
import { toast } from "react-toastify";

import { constructPath } from "@/shared/api/rest/fetch";
import { ModalConfirm } from "@/shared/components/modals/modal-confirm";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Link } from "@/shared/components/ui/link";
import { classNames } from "@/shared/utils/common";

import type { retryTask } from "@/entities/tasks/domain/retry-task/retry-task";
import { useCancelTaskMutation } from "@/entities/tasks/ui/queries/cancel-task.mutation";
import { useRetryTaskMutation } from "@/entities/tasks/ui/queries/retry-task.mutation";
import { tasksQueryKeys } from "@/entities/tasks/ui/queries/tasks.query-keys";

type TaskAction = {
  action: string | null;
  available: boolean | null;
  unavailability_reason?: string | null;
};

export type TaskActionsTask = {
  id?: string | null;
  title?: string | null;
  state?: string | null;
  available_actions?: (TaskAction | null)[] | null;
};

const formatState = (state?: string | null) => {
  if (!state) return "settled";
  return state.charAt(0).toUpperCase() + state.slice(1).toLowerCase();
};

const isActionAvailable = (task: TaskActionsTask, action: string) =>
  (task.available_actions ?? []).some((entry) => entry?.action === action && entry?.available);

export const TaskActions = ({ task, className }: { task: TaskActionsTask; className?: string }) => {
  const queryClient = useQueryClient();
  const { pathname } = useLocation();
  const [isRetryConfirmOpen, setIsRetryConfirmOpen] = useState(false);
  const [isCancelConfirmOpen, setIsCancelConfirmOpen] = useState(false);

  const retryMutation = useRetryTaskMutation({
    onSuccess: async (result: Awaited<ReturnType<typeof retryTask>>) => {
      setIsRetryConfirmOpen(false);
      // The new run is a sibling of the current one, so swap the task id in the path we are
      // already on. This keeps the link pointing at whichever task view the retry was triggered
      // from — the standalone task page or an object's task tab.
      const newRunPath = constructPath(`${pathname.replace(/\/[^/]+\/?$/, "")}/${result}`);
      const message = result ? (
        <>
          Task retried.{" "}
          <Link to={newRunPath} className="inline-flex items-center gap-1 underline">
            View new run <ArrowUpRightIcon className="size-3.5" />
          </Link>
        </>
      ) : (
        "Task retried."
      );
      toast(<Alert type={ALERT_TYPES.SUCCESS} message={message} />);
      await queryClient.invalidateQueries({ queryKey: tasksQueryKeys.all });
    },
    onError: (error: Error) => {
      toast(<Alert type={ALERT_TYPES.ERROR} message={`Error: ${error.message}`} />);
    },
  });

  const cancelMutation = useCancelTaskMutation({
    onSuccess: async () => {
      setIsCancelConfirmOpen(false);
      toast(<Alert type={ALERT_TYPES.SUCCESS} message="Task cancelled." />);
      await queryClient.invalidateQueries({ queryKey: tasksQueryKeys.all });
    },
    onError: (error: Error) => {
      toast(<Alert type={ALERT_TYPES.ERROR} message={`Error: ${error.message}`} />);
    },
  });

  if (!task.id) return null;

  const canRetry = isActionAvailable(task, "RETRY");
  const canCancel = isActionAvailable(task, "CANCEL");

  return (
    <div className={classNames("flex items-center gap-2", className)}>
      {canRetry && (
        <Button
          variant="outline"
          onPress={() => setIsRetryConfirmOpen(true)}
          className="flex items-center gap-2"
        >
          <Icon icon="mdi:restore" />
          Retry
        </Button>
      )}

      {canCancel && (
        <Button
          variant="outline"
          onPress={() => setIsCancelConfirmOpen(true)}
          className="flex items-center gap-2"
        >
          <Icon icon="mdi:close" />
          Cancel
        </Button>
      )}

      <ModalConfirm
        isOpen={isRetryConfirmOpen}
        onOpenChange={setIsRetryConfirmOpen}
        title={`Retry "${task.title ?? "this"}" task?`}
        description={`This creates a new task with the same settings. The current one stays ${formatState(task.state)}. Track progress in the new run.`}
        confirmLabel="Retry"
        icon="mdi:restore"
        iconClassName="text-gray-500"
        iconContainerClassName="bg-gray-100"
        isLoading={retryMutation.isPending}
        onConfirm={() => retryMutation.mutate({ id: task.id as string })}
      />

      <ModalConfirm
        isOpen={isCancelConfirmOpen}
        onOpenChange={setIsCancelConfirmOpen}
        title={`Cancel "${task.title ?? "this"}" task?`}
        description="This stops the task and skips its remaining retries. It will be marked cancelled and won't run again."
        confirmLabel="Cancel task"
        cancelLabel="Keep task"
        confirmVariant="danger"
        icon="mdi:alert"
        iconClassName="text-red-600"
        iconContainerClassName="bg-red-100"
        isLoading={cancelMutation.isPending}
        onConfirm={() => cancelMutation.mutate({ id: task.id as string })}
      />
    </div>
  );
};
