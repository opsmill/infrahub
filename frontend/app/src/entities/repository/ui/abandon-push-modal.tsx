import { toast } from "react-toastify";

import { Col } from "@/shared/components/container";
import { ModalDanger } from "@/shared/components/modals/modal-danger";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { pluralize } from "@/shared/utils/string";

import { useDefaultBranch } from "@/entities/branches/ui/hooks/use-default-branch";
import { PendingMergeList } from "@/entities/repository/ui/pending-merge-list";
import { useAbandonPushMutation } from "@/entities/repository/ui/queries/abandon-push.mutation";
import { useGetRepositoryPushState } from "@/entities/repository/ui/queries/get-repository-push-state.query";
import { toastTaskStarted } from "@/entities/repository/ui/toast-task-started";

interface AbandonPushModalProps {
  repositoryId: string;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
}

export function AbandonPushModal({ repositoryId, isOpen, onOpenChange }: AbandonPushModalProps) {
  const { data: pushState } = useGetRepositoryPushState({ repositoryId });
  const defaultBranch = useDefaultBranch();
  const pendingMerges = pushState?.pendingMerges ?? [];
  const { mutate: abandonPush, isPending } = useAbandonPushMutation({
    onSuccess: (result) => {
      toastTaskStarted("Started abandoning the pending pushes.", result.taskId);
    },
    onError: (error) => {
      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message={`Error abandoning the pending pushes: ${error.message}`}
        />
      );
    },
    // After a refusal the list shown is out of date, so the user reopens the modal to read the new one.
    onSettled: () => onOpenChange(false),
  });

  return (
    <ModalDanger
      title="Abandon pending push"
      description={
        <Col className="gap-3">
          <p className="text-foreground">
            {pluralize(pendingMerges.length, "merge")} won't be pushed to the remote
          </p>
          <div className="max-h-60 overflow-y-auto rounded-md border bg-content-muted px-3 py-2">
            <PendingMergeList merges={pendingMerges} />
          </div>
          <ul className="flex flex-col gap-1 text-xs">
            <li>The remote stays as it is, and no branch is deleted</li>
            <li>
              Objects from these merges stay on {defaultBranch?.name ?? "the default branch"} until
              you reimport the current commit
            </li>
          </ul>
        </Col>
      }
      confirmLabel="Abandon"
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      isLoading={isPending}
      // The version names the list shown, so the backend refuses to abandon if the pending merges changed since.
      onConfirm={() =>
        pushState && abandonPush({ repositoryId, queueVersion: pushState.queueVersion })
      }
    />
  );
}
