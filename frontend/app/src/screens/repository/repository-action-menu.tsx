import { Icon } from "@iconify-icon/react";

import { Button, ButtonWithTooltip } from "@/components/buttons/button-primitive";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  CHECK_REPOSITORY_CONNECTIVITY,
  REIMPORT_LAST_COMMIT,
} from "@/graphql/mutations/repository/actions";
import { useMutation } from "@/hooks/useQuery";
import { Dialog } from "@headlessui/react";
import { useState } from "react";
import { toast } from "react-toastify";

const RepositoryActionMenu = ({ repositoryId }: { repositoryId: string }) => {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <ButtonWithTooltip
            tooltipContent="More"
            tooltipEnabled
            variant="ghost"
            size="square"
            className="p-4"
          >
            <Icon icon="mdi:dots-vertical" className="text-custom-blue-900 text-lg p-4" />
          </ButtonWithTooltip>
        </DropdownMenuTrigger>

        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => setIsOpen(true)}>
            <Icon icon="mdi:access-point" className="text-lg" />
            Check connectivity
          </DropdownMenuItem>

          <ReimportLastCommitAction repositoryId={repositoryId} />
        </DropdownMenuContent>
      </DropdownMenu>

      <CheckConnectivityModal repositoryId={repositoryId} isOpen={isOpen} setIsOpen={setIsOpen} />
    </>
  );
};

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

  return (
    <>
      <Dialog open={isOpen} onClose={() => setIsOpen(false)}>
        <div className="fixed inset-0 flex w-screen items-center justify-center bg-gray-600/25">
          <Dialog.Panel className="bg-white p-4 border rounded-lg max-w-lg space-y-4">
            <Dialog.Title className="font-semibold text-lg">
              Check{loading && "ing"} repository connectivity
            </Dialog.Title>

            <Dialog.Description>
              Are you sure you want to check the connectivity to this repository? This will validate
              your connection and authentication status.
            </Dialog.Description>

            <div className="text-right space-x-2">
              <Button variant="outline" onClick={handleClose}>
                Cancel
              </Button>
              <Button isLoading={loading} disabled={loading} onClick={() => checkConnectivity()}>
                Check now
              </Button>
            </div>

            <Dialog open={called && !loading} onClose={handleClose}>
              <div className="fixed inset-0 flex w-screen items-center justify-center">
                <Dialog.Panel className="bg-white p-4 border rounded-lg max-w-lg space-y-4">
                  <Dialog.Title className="font-semibold text-lg">
                    Connection {isConnectivityOk ? "Successful" : "Failed"}
                  </Dialog.Title>

                  <Dialog.Description>
                    {data?.InfrahubRepositoryConnectivity?.message || error?.message}
                  </Dialog.Description>

                  {isConnectivityOk && (
                    <Button variant="active" onClick={handleClose}>
                      Done
                    </Button>
                  )}

                  {!isConnectivityOk && (
                    <div className="text-right space-x-2">
                      <Button variant="outline" onClick={handleClose}>
                        Cancel
                      </Button>

                      <Button variant="danger" onClick={() => checkConnectivity()}>
                        Retry
                      </Button>
                    </div>
                  )}
                </Dialog.Panel>
              </div>
            </Dialog>
          </Dialog.Panel>
        </div>
      </Dialog>
    </>
  );
};

const ReimportLastCommitAction = ({ repositoryId }: { repositoryId: string }) => {
  const [reimportLastCommit] = useMutation(REIMPORT_LAST_COMMIT, {
    variables: {
      repositoryId,
    },
    onCompleted: (data) => {
      if (data?.InfrahubRepositoryProcess?.ok) {
        toast(
          <Alert
            type={ALERT_TYPES.SUCCESS}
            message='Reimport of last commit started. You can view its status on the "Tasks" tab.'
          />
        );
      }
    },
  });

  return (
    <DropdownMenuItem onClick={() => reimportLastCommit()}>
      <Icon icon="mdi:reload" className="text-lg" />
      Reimport last commit
    </DropdownMenuItem>
  );
};

export default RepositoryActionMenu;
