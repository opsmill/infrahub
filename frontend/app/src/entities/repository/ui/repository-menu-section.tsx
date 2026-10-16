import { MenuItem, MenuSection } from "@infrahub/ui";
import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { Icon } from "@/shared/components/display/icon";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import {
  EDIT_DEFAULT_BRANCH,
  MANAGE_REPOSITORIES,
  type Permission,
} from "@/entities/permission/domain/model/permission";
import { useHasGlobalPermission } from "@/entities/permission/ui/queries/has-global-permission.query";
import { REPOSITORY_KIND } from "@/entities/repository/domain/model/repository";
import type { RepositoryPushState } from "@/entities/repository/domain/model/repository-push-state";
import { getPushActions } from "@/entities/repository/domain/rules/get-push-actions";
import { isReadOnlyRepository } from "@/entities/repository/domain/rules/is-read-only-repository";
import { useGetRepositoryPushState } from "@/entities/repository/ui/queries/get-repository-push-state.query";
import { useImportCurrentCommitMutation } from "@/entities/repository/ui/queries/import-current-commit.mutation";
import { useReimportLastCommitMutation } from "@/entities/repository/ui/queries/reimport-last-commit.mutation";
import { useRetryPushMutation } from "@/entities/repository/ui/queries/retry-push.mutation";
import { toastTaskStarted } from "@/entities/repository/ui/toast-task-started";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";

interface RepositoryMenuSectionProps {
  repositoryId: string;
  objectSchema: ModelSchema;
  onCheckConnectivity: () => void;
  onAbandonPush: (pushState: RepositoryPushState) => void;
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
        <RepositoryPushMenuItems
          repositoryId={repositoryId}
          isUpdateAllowed={isUpdateAllowed}
          onAbandonPush={onAbandonPush}
        />
      )}
    </MenuSection>
  );
}

interface RepositoryPushMenuItemsProps {
  repositoryId: string;
  isUpdateAllowed: boolean;
  onAbandonPush: (pushState: RepositoryPushState) => void;
}

function RepositoryPushMenuItems({
  repositoryId,
  isUpdateAllowed,
  onAbandonPush,
}: RepositoryPushMenuItemsProps) {
  const { data: state, isError } = useGetRepositoryPushState({ repositoryId });
  // Until the state loads, nothing is known to be pending.
  const { canRetry, canAbandon } = getPushActions(
    isError ? "unreadable" : (state?.status ?? "none")
  );
  // The backend checks both global permissions for an action on the pending pushes.
  const { data: canManageRepositories = false } = useHasGlobalPermission(MANAGE_REPOSITORIES);
  const { data: canEditDefaultBranch = false } = useHasGlobalPermission(EDIT_DEFAULT_BRANCH);
  const isAllowed = isUpdateAllowed && canManageRepositories && canEditDefaultBranch;

  const { mutate: retryPush } = useRetryPushMutation({
    onSuccess: async (result) => {
      toastTaskStarted("Retry of the pending pushes started.", result.taskId);
      await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
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
      <MenuItem isDisabled={!isAllowed || !canRetry} onAction={() => retryPush({ repositoryId })}>
        <Icon icon="mdi:upload" />
        Retry push
      </MenuItem>

      <MenuItem
        isDisabled={!isAllowed || !canAbandon}
        onAction={() => state && onAbandonPush(state)}
      >
        <Icon icon="mdi:upload-off" />
        Abandon pending push
      </MenuItem>
    </>
  );
}
