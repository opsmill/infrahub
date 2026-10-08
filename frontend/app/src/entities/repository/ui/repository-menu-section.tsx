import { MenuItem, MenuSection } from "@infrahub/ui";
import { ArrowUpRightIcon } from "lucide-react";
import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { constructPath } from "@/shared/api/rest/fetch";
import { Icon } from "@/shared/components/display/icon";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Link } from "@/shared/components/ui/link";

import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import type { Permission } from "@/entities/permission/domain/model/permission";
import {
  READONLY_REPOSITORY_KIND,
  REPOSITORY_KIND,
} from "@/entities/repository/domain/model/repository";
import { getDeliveryActions } from "@/entities/repository/domain/rules/get-delivery-actions";
import { useGetDeliveryState } from "@/entities/repository/ui/queries/get-delivery-state.query";
import { useImportCurrentCommitMutation } from "@/entities/repository/ui/queries/import-current-commit.mutation";
import { useReimportLastCommitMutation } from "@/entities/repository/ui/queries/reimport-last-commit.mutation";
import { useRetryDeliveryMutation } from "@/entities/repository/ui/queries/retry-delivery.mutation";
import { DELIVERY_TEXTS } from "@/entities/repository/ui/repository-delivery-texts";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";

interface RepositoryMenuSectionProps {
  repositoryId: string;
  objectSchema: ModelSchema;
  onCheckConnectivity: () => void;
  permission: Permission;
}

export function RepositoryMenuSection({
  repositoryId,
  objectSchema,
  onCheckConnectivity,
  permission,
}: RepositoryMenuSectionProps) {
  const isReadOnlyRepository = isOfKind(READONLY_REPOSITORY_KIND, objectSchema);
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

      {isReadOnlyRepository && (
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
        />
      )}
    </MenuSection>
  );
}

interface RepositoryDeliveryMenuItemsProps {
  repositoryId: string;
  isUpdateAllowed: boolean;
}

function RepositoryDeliveryMenuItems({
  repositoryId,
  isUpdateAllowed,
}: RepositoryDeliveryMenuItemsProps) {
  const { data: state } = useGetDeliveryState({ repositoryId });
  // Until the state loads, nothing is known to be pending.
  const { canRetry } = getDeliveryActions(state?.status ?? "none");

  const { mutate: retryDelivery } = useRetryDeliveryMutation({
    onSuccess: async (result) => {
      toastTaskStarted(DELIVERY_TEXTS.retryStarted, result.taskId);
      await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
    },
    onError: (error) => {
      toast(
        <Alert
          type={ALERT_TYPES.ERROR}
          message={`${DELIVERY_TEXTS.retryFailed} ${error.message}`}
        />
      );
    },
  });

  return (
    <MenuItem
      isDisabled={!isUpdateAllowed || !canRetry}
      onAction={() => retryDelivery({ repositoryId })}
    >
      <Icon icon="mdi:upload" />
      {DELIVERY_TEXTS.retry}
    </MenuItem>
  );
}

function toastTaskStarted(startedMessage: string, taskId?: string) {
  const message = taskId ? (
    <>
      {startedMessage}
      <br />
      <Link
        to={constructPath(`/tasks/${taskId}`)}
        className="inline-flex items-center gap-1 underline"
      >
        View task <ArrowUpRightIcon className="size-3.5" />
      </Link>
    </>
  ) : (
    `${startedMessage} You can view its status on the "Tasks" tab.`
  );
  toast(<Alert type={ALERT_TYPES.SUCCESS} message={message} />);
}
