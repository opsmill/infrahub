import { MenuItem, MenuSection } from "@infrahub/ui";
import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { Icon } from "@/shared/components/display/icon";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import type { Permission } from "@/entities/permission/domain/model/permission";
import { REPOSITORY_KIND } from "@/entities/repository/domain/model/repository";
import { getPushActions } from "@/entities/repository/domain/rules/get-push-actions";
import { isReadOnlyRepository } from "@/entities/repository/domain/rules/is-read-only-repository";
import {
  ACCESS_DENIED_TOOLTIP,
  usePendingPushPermissions,
} from "@/entities/repository/ui/hooks/use-pending-push-permissions";
import { useGetRepositoryPushState } from "@/entities/repository/ui/queries/get-repository-push-state.query";
import { useImportCurrentCommitMutation } from "@/entities/repository/ui/queries/import-current-commit.mutation";
import { useReimportLastCommitMutation } from "@/entities/repository/ui/queries/reimport-last-commit.mutation";
import { useRetryRepositoryPushMutation } from "@/entities/repository/ui/queries/retry-repository-push.mutation";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";
import { toastTaskStarted } from "@/entities/tasks/ui/toast-task-started";

interface RepositoryMenuSectionProps {
  repositoryId: string;
  objectSchema: ModelSchema;
  onCheckConnectivity: () => void;
  onAbandonPush: () => void;
  permission: Permission;
}

export function RepositoryMenuSection({
  repositoryId,
  objectSchema,
  onCheckConnectivity,
  onAbandonPush,
  permission,
}: RepositoryMenuSectionProps) {
  const isReadOnly = isReadOnlyRepository(objectSchema);
  const isUpdateAllowed = permission.update.isAllowed;

  const { mutate: reimportLastCommit } = useReimportLastCommitMutation({
    onSuccess: async (result) => {
      toastTaskStarted("Import from remote started.", result.taskId);
      await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
    },
    onError: (error) => {
      toast(
        <Alert type={ALERT_TYPES.ERROR} message={`Error importing from remote: ${error.message}`} />
      );
    },
  });

  const { mutate: importCurrentCommit } = useImportCurrentCommitMutation({
    onSuccess: async (result) => {
      toastTaskStarted("Import of current commit started.", result.taskId);
      await queryClient.invalidateQueries({
        queryKey: objectQueryKeys.all,
      });
    },
    onError: (error) => {
      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message={`Error importing current commit: ${error.message}`}
        />
      );
    },
  });

  return (
    <MenuSection title="Repository">
      <MenuItem onAction={onCheckConnectivity}>
        <Icon icon="mdi:access-point" />
        Check connectivity
      </MenuItem>

      {isReadOnly && (
        <MenuItem
          isDisabled={!isUpdateAllowed}
          onAction={() => reimportLastCommit({ repositoryId })}
        >
          <Icon icon="mdi:source-commit" />
          Import latest commit
        </MenuItem>
      )}

      <MenuItem
        isDisabled={!isUpdateAllowed}
        onAction={() => importCurrentCommit({ repositoryId })}
      >
        <Icon icon="mdi:reload" />
        Reimport current commit
      </MenuItem>

      {isOfKind(REPOSITORY_KIND, objectSchema) && (
        <RepositoryPushMenuItems repositoryId={repositoryId} onAbandonPush={onAbandonPush} />
      )}
    </MenuSection>
  );
}

const NOTHING_TO_PUSH_TOOLTIP = "Nothing to push";
const UNREADABLE_PUSH_STATE_TOOLTIP = "Couldn't load the pending pushes. Reload the page";

interface RepositoryPushMenuItemsProps {
  repositoryId: string;
  onAbandonPush: () => void;
}

function RepositoryPushMenuItems({ repositoryId, onAbandonPush }: RepositoryPushMenuItemsProps) {
  const { data: state, isPending, isError } = useGetRepositoryPushState({ repositoryId });
  const permissions = usePendingPushPermissions();
  // Until the state loads, nothing is known to be pending.
  const pushActions = getPushActions(state?.status ?? "none");
  // The backend refuses a retry when nothing is pending, so an unreadable state still allows one.
  const canRetry = isError || pushActions.canRetry;
  // A failed reload keeps the last state, whose queue version the backend would refuse.
  const canAbandon = !isError && pushActions.canAbandon;

  const accessTooltip =
    permissions.isPending || permissions.canActOnPendingPushes ? undefined : ACCESS_DENIED_TOOLTIP;
  const retryTooltip =
    accessTooltip ?? (isPending || canRetry ? undefined : NOTHING_TO_PUSH_TOOLTIP);
  const abandonTooltip =
    accessTooltip ?? getAbandonStateTooltip({ isPending, isError, canAbandon });

  const { mutate: retryRepositoryPush, isPending: isRetrying } = useRetryRepositoryPushMutation({
    onSuccess: (result) => {
      toastTaskStarted("Retry of the pending pushes started.", result.taskId);
    },
    onError: (error) => {
      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message={`Error retrying the pending pushes: ${error.message}`}
        />
      );
    },
  });

  return (
    <>
      <MenuItem
        isDisabled={!permissions.canActOnPendingPushes || !canRetry || isRetrying}
        tooltip={retryTooltip}
        onAction={() => retryRepositoryPush({ repositoryId })}
      >
        <Icon icon="mdi:upload" />
        Retry push
      </MenuItem>

      <MenuItem
        isDisabled={!permissions.canActOnPendingPushes || !canAbandon}
        tooltip={abandonTooltip}
        onAction={onAbandonPush}
      >
        <Icon icon="mdi:upload-off" />
        Abandon pending push
      </MenuItem>
    </>
  );
}

interface GetAbandonStateTooltipParams {
  isPending: boolean;
  isError: boolean;
  canAbandon: boolean;
}

function getAbandonStateTooltip({ isPending, isError, canAbandon }: GetAbandonStateTooltipParams) {
  if (isError) return UNREADABLE_PUSH_STATE_TOOLTIP;
  if (isPending || canAbandon) return;
  return NOTHING_TO_PUSH_TOOLTIP;
}
