import { MenuItem, MenuSection } from "@infrahub/ui";
import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { Icon } from "@/shared/components/display/icon";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import type { Permission } from "@/entities/permission/domain/model/permission";
import { REPOSITORY_KIND } from "@/entities/repository/domain/model/repository";
import type { RepositoryPushState } from "@/entities/repository/domain/model/repository-push-state";
import { getPushActions } from "@/entities/repository/domain/rules/get-push-actions";
import { isReadOnlyRepository } from "@/entities/repository/domain/rules/is-read-only-repository";
import { useGetRepositoryPushState } from "@/entities/repository/ui/queries/get-repository-push-state.query";
import { useImportCurrentCommitMutation } from "@/entities/repository/ui/queries/import-current-commit.mutation";
import { useReimportLastCommitMutation } from "@/entities/repository/ui/queries/reimport-last-commit.mutation";
import { useRetryDeliveryMutation } from "@/entities/repository/ui/queries/retry-delivery.mutation";
import { toastTaskStarted } from "@/entities/repository/ui/toast-task-started";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";

interface RepositoryMenuSectionProps {
  repositoryId: string;
  objectSchema: ModelSchema;
  onCheckConnectivity: () => void;
  onAbandonDelivery: (deliveryState: RepositoryPushState) => void;
  permission: Permission;
}

export function RepositoryMenuSection({
  repositoryId,
  objectSchema,
  onCheckConnectivity,
  onAbandonDelivery,
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

      <MenuItem onAction={() => importCurrentCommit({ repositoryId })}>
        <Icon icon="mdi:reload" />
        Reimport current commit
      </MenuItem>

      {isOfKind(REPOSITORY_KIND, objectSchema) && (
        <RepositoryDeliveryMenuItems
          repositoryId={repositoryId}
          isUpdateAllowed={isUpdateAllowed}
          onAbandonDelivery={onAbandonDelivery}
        />
      )}
    </MenuSection>
  );
}

interface RepositoryDeliveryMenuItemsProps {
  repositoryId: string;
  isUpdateAllowed: boolean;
  onAbandonDelivery: (deliveryState: RepositoryPushState) => void;
}

function RepositoryDeliveryMenuItems({
  repositoryId,
  isUpdateAllowed,
  onAbandonDelivery,
}: RepositoryDeliveryMenuItemsProps) {
  const { data: state } = useGetRepositoryPushState({ repositoryId });
  // Until the state loads, nothing is known to be pending.
  const { canRetry, canAbandon } = getPushActions(state?.status ?? "none");

  const { mutate: retryDelivery } = useRetryDeliveryMutation({
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
      <MenuItem
        isDisabled={!isUpdateAllowed || !canRetry}
        onAction={() => retryDelivery({ repositoryId })}
      >
        <Icon icon="mdi:upload" />
        Retry push
      </MenuItem>

      <MenuItem
        isDisabled={!isUpdateAllowed || !canAbandon}
        onAction={() => state && onAbandonDelivery(state)}
      >
        <Icon icon="mdi:upload-off" />
        Abandon pending push
      </MenuItem>
    </>
  );
}
