import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { ModalDanger } from "@/shared/components/modals/modal-danger";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
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
    onSettled: async () => {
      onOpenChange(false);
      await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
    },
  });

  return (
    <ModalDanger
      title="Abandon pending push"
      description={
        <div className="flex flex-col gap-2">
          <p>Abandon every pending merge of this repository:</p>
          <PendingMergeList merges={pushState?.pendingMerges ?? []} />
          <p>Nothing is removed from the remote, and no remote branch is deleted.</p>
          <p>
            Repository objects of the abandoned merges can stay on the default branch until the
            current commit is reimported.
          </p>
        </div>
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
