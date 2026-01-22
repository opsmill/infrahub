import { Heading } from "react-aria-components";

import { Modal } from "@/shared/components/aria/modal";
import { Button } from "@/shared/components/buttons/button-primitive";
import { Col, Row } from "@/shared/components/container";

import { useCheckConnectivityMutation } from "@/entities/repository/domain/check-connectivity.mutation";

interface CheckConnectivityModalProps {
  repositoryId: string;
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CheckConnectivityModal({
  isOpen,
  onOpenChange,
  repositoryId,
}: CheckConnectivityModalProps) {
  const {
    mutate: checkConnectivity,
    isPending,
    data,
    error,
    isSuccess,
  } = useCheckConnectivityMutation();

  const handleClose = () => {
    onOpenChange(false);
  };

  const isConnectivityOk = data?.ok;
  const showResult = isSuccess || error;

  return (
    <Modal
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      isDismissable={!isPending}
      className="w-full max-w-lg"
    >
      <Col className="gap-4 p-2">
        {!showResult ? (
          <>
            <Heading slot="title" className="font-semibold text-lg">
              Check{isPending && "ing"} repository connectivity
            </Heading>

            <p>
              Check the connectivity to this repository to validate your connection and
              authentication status.
            </p>

            <Row className="justify-end">
              <Button variant="outline" onClick={handleClose}>
                Cancel
              </Button>
              <Button
                isLoading={isPending}
                disabled={isPending}
                onClick={() => checkConnectivity({ repositoryId })}
              >
                Check now
              </Button>
            </Row>
          </>
        ) : (
          <>
            <Heading slot="title" className="font-semibold text-lg">
              Connection {isConnectivityOk ? "Successful" : "Failed"}
            </Heading>

            <p>{data?.message || error?.message}</p>

            <Row className="justify-end">
              {isConnectivityOk ? (
                <Button variant="active" onClick={handleClose}>
                  Done
                </Button>
              ) : (
                <>
                  <Button variant="outline" onClick={handleClose}>
                    Cancel
                  </Button>

                  <Button variant="danger" onClick={() => checkConnectivity({ repositoryId })}>
                    Retry
                  </Button>
                </>
              )}
            </Row>
          </>
        )}
      </Col>
    </Modal>
  );
}
