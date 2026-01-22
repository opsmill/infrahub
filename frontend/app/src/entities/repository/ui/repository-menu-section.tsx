import { Icon } from "@iconify-icon/react";
import { ArrowUpRightIcon } from "lucide-react";
import { toast } from "react-toastify";

import { queryClient } from "@/shared/api/rest/client";
import { constructPath } from "@/shared/api/rest/fetch";
import { MenuItem, MenuSection } from "@/shared/components/aria/menu";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Link } from "@/shared/components/ui/link";
import { READONLY_REPOSITORY_KIND } from "@/shared/config/constants";

import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import type { Permission } from "@/entities/permission/types";
import { useImportCurrentCommitMutation } from "@/entities/repository/domain/import-current-commit.mutation";
import { useReimportLastCommitMutation } from "@/entities/repository/domain/reimport-last-commit.mutation";
import type { ModelSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

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
      const message = result.taskId ? (
        <>
          Import from remote started.
          <br />
          <Link
            to={constructPath(`/tasks/${result.taskId}`)}
            className="inline-flex items-center gap-1 underline"
          >
            View task <ArrowUpRightIcon className="size-3.5" />
          </Link>
        </>
      ) : (
        'Import from remote started. You can view its status on the "Tasks" tab.'
      );
      toast(<Alert type={ALERT_TYPES.SUCCESS} message={message} />);
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
      const message = result.taskId ? (
        <>
          Import of current commit started.
          <br />
          <Link
            to={constructPath(`/tasks/${result.taskId}`)}
            className="inline-flex items-center gap-1 underline"
          >
            View task <ArrowUpRightIcon className="size-3.5" />
          </Link>
        </>
      ) : (
        'Import of current commit started. You can view its status on the "Tasks" tab.'
      );
      toast(<Alert type={ALERT_TYPES.SUCCESS} message={message} />);
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

      <MenuItem isDisabled={!isUpdateAllowed} onAction={() => reimportLastCommit({ repositoryId })}>
        <Icon icon="mdi:source-commit" />
        Import latest commit
      </MenuItem>

      {isReadOnlyRepository && (
        <MenuItem onAction={() => importCurrentCommit({ repositoryId })}>
          <Icon icon="mdi:reload" />
          Reimport current commit
        </MenuItem>
      )}
    </MenuSection>
  );
}
