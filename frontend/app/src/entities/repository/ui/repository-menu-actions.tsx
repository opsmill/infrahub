import { Dialog } from "@headlessui/react";
import { Icon } from "@iconify-icon/react";
import { ArrowUpRightIcon } from "lucide-react";
import { toast } from "react-toastify";

import { useMutation } from "@/shared/api/graphql/useQuery";
import { queryClient } from "@/shared/api/rest/client";
import { constructPath } from "@/shared/api/rest/fetch";
import { MenuItem, MenuSection } from "@/shared/components/aria/menu";
import { Button } from "@/shared/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Link } from "@/shared/components/ui/link";
import { READONLY_REPOSITORY_KIND } from "@/shared/config/constants";

import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import type { Permission } from "@/entities/permission/types";
import {
  CHECK_REPOSITORY_CONNECTIVITY,
  IMPORT_READONLY_REPOSITORY_LAST_COMMIT,
  REIMPORT_LAST_COMMIT,
} from "@/entities/repository/api/actions";
import type { ModelSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

interface RepositoryMenuSectionProps {
  onCheckConnectivity: () => void;
  onImportLatestCommit: () => void;
  onReimportCurrentCommit?: () => void;
  permission: Permission;
}

export function RepositoryMenuSection({
  onCheckConnectivity,
  onImportLatestCommit,
  onReimportCurrentCommit,
  permission,
}: RepositoryMenuSectionProps) {
  const isUpdateAllowed = permission.update.isAllowed;

  return (
    <MenuSection>
      <MenuItem onAction={onCheckConnectivity}>
        <Icon icon="mdi:access-point" />
        Check connectivity
      </MenuItem>

      <MenuItem isDisabled={!isUpdateAllowed} onAction={onImportLatestCommit}>
        <Icon icon="mdi:source-commit" />
        Import latest commit
      </MenuItem>

      {onReimportCurrentCommit && (
        <MenuItem onAction={onReimportCurrentCommit}>
          <Icon icon="mdi:reload" />
          Reimport current commit
        </MenuItem>
      )}
    </MenuSection>
  );
}

interface RepositoryActionsMenuProps {
  repositoryId: string;
  objectSchema: ModelSchema;
  onCheckConnectivity: () => void;
  permission: Permission;
}

export function RepositoryActionsMenu({
  repositoryId,
  objectSchema,
  onCheckConnectivity,
  permission,
}: RepositoryActionsMenuProps) {
  const isReadOnlyRepository = isOfKind(READONLY_REPOSITORY_KIND, objectSchema);

  const [reimportLastCommit] = useMutation(REIMPORT_LAST_COMMIT, {
    variables: {
      repositoryId,
    },
    onCompleted: async (data) => {
      if (data?.InfrahubRepositoryProcess?.ok) {
        const taskId = data.InfrahubRepositoryProcess.task?.id;
        const message = taskId ? (
          <>
            Import from remote started.
            <br />
            <Link
              to={constructPath(`/tasks/${taskId}`)}
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
      } else {
        toast(<Alert type={ALERT_TYPES.ERROR} message="Failed to start import from remote." />);
      }
    },
    onError: (error) => {
      toast(
        <Alert type={ALERT_TYPES.ERROR} message={`Error importing from remote: ${error.message}`} />
      );
    },
  });

  const [importCurrentCommit] = useMutation(IMPORT_READONLY_REPOSITORY_LAST_COMMIT, {
    variables: {
      id: repositoryId,
    },
    onCompleted: async (data) => {
      if (data?.InfrahubReadOnlyRepositoryImportLastCommit?.ok) {
        const taskId = data.InfrahubReadOnlyRepositoryImportLastCommit.task?.id;
        const message = taskId ? (
          <>
            Import of current commit started.
            <br />
            <Link
              to={constructPath(`/tasks/${taskId}`)}
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
      } else {
        toast(
          <Alert type={ALERT_TYPES.ERROR} message="Failed to start import of current commit." />
        );
      }
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
    <RepositoryMenuSection
      onCheckConnectivity={onCheckConnectivity}
      onImportLatestCommit={() => reimportLastCommit()}
      onReimportCurrentCommit={isReadOnlyRepository ? () => importCurrentCommit() : undefined}
      permission={permission}
    />
  );
}

interface RepositoryActionsModalProps {
  repositoryId: string;
  isOpen: boolean;
  onClose: () => void;
}

export function RepositoryActionsModal({
  repositoryId,
  isOpen,
  onClose,
}: RepositoryActionsModalProps) {
  return <CheckConnectivityModal repositoryId={repositoryId} isOpen={isOpen} setIsOpen={onClose} />;
}

const CheckConnectivityModal = ({
  isOpen,
  setIsOpen,
  repositoryId,
}: {
  isOpen: boolean;
  setIsOpen: (b: boolean) => void;
  repositoryId: string;
}) => {
  const [checkConnectivity, { loading, data, error, called, reset }] = useMutation(
    CHECK_REPOSITORY_CONNECTIVITY,
    {
      variables: { repositoryId },
    }
  );

  const handleClose = () => {
    setIsOpen(false);
    reset();
  };

  const isConnectivityOk = data?.InfrahubRepositoryConnectivity?.ok;
  const showResult = called && !loading;

  return (
    <Dialog open={isOpen} onClose={handleClose}>
      <div className="fixed inset-0 flex w-screen items-center justify-center bg-gray-600/25">
        <Dialog.Panel className="max-w-lg space-y-4 rounded-lg border border-gray-200 bg-white p-4">
          {!showResult ? (
            <>
              <Dialog.Title className="font-semibold text-lg">
                Check{loading && "ing"} repository connectivity
              </Dialog.Title>

              <Dialog.Description>
                Check the connectivity to this repository to validate your connection and
                authentication status.
              </Dialog.Description>

              <div className="space-x-2 text-right">
                <Button variant="outline" onClick={handleClose}>
                  Cancel
                </Button>
                <Button isLoading={loading} disabled={loading} onClick={() => checkConnectivity()}>
                  Check now
                </Button>
              </div>
            </>
          ) : (
            <>
              <Dialog.Title className="font-semibold text-lg">
                Connection {isConnectivityOk ? "Successful" : "Failed"}
              </Dialog.Title>

              <Dialog.Description>
                {data?.InfrahubRepositoryConnectivity?.message || error?.message}
              </Dialog.Description>

              {isConnectivityOk ? (
                <div className="text-right">
                  <Button variant="active" onClick={handleClose}>
                    Done
                  </Button>
                </div>
              ) : (
                <div className="space-x-2 text-right">
                  <Button variant="outline" onClick={handleClose}>
                    Cancel
                  </Button>

                  <Button variant="danger" onClick={() => checkConnectivity()}>
                    Retry
                  </Button>
                </div>
              )}
            </>
          )}
        </Dialog.Panel>
      </div>
    </Dialog>
  );
};
