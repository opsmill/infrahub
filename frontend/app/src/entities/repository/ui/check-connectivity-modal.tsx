import { Heading } from "react-aria-components";

import { Modal } from "@/shared/components/aria/modal";
import { Col, Row } from "@/shared/components/container";
import { Button } from "@/shared/components/ui/button";

import { useCheckConnectivityMutation } from "@/entities/repository/ui/queries/check-connectivity.mutation";

interface CheckConnectivityLayoutProps {
  title: React.ReactNode;
  description: React.ReactNode;
  actions: React.ReactNode;
}

function CheckConnectivityLayout({ title, description, actions }: CheckConnectivityLayoutProps) {
  return (
    <Col className="gap-4 p-2">
      <Heading slot="title" className="font-semibold text-lg">
        {title}
      </Heading>
      <p>{description}</p>
      <Row className="justify-end">{actions}</Row>
    </Col>
  );
}

interface CheckConnectivityProps {
  repositoryId: string;
  onClose: () => void;
}

function CheckConnectivity({ repositoryId, onClose }: CheckConnectivityProps) {
  const {
    mutate: checkConnectivity,
    isPending,
    data,
    error,
    isSuccess,
  } = useCheckConnectivityMutation();

  if (isPending) {
    return (
      <CheckConnectivityLayout
        title="Checking repository connectivity"
        description="Check the connectivity to this repository to validate your connection and authentication status."
        actions={
          <>
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button isLoading disabled>
              Check now
            </Button>
          </>
        }
      />
    );
  }

  if (error) {
    return (
      <CheckConnectivityLayout
        title="Connection Failed"
        description={error.message}
        actions={
          <>
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="danger" onClick={() => checkConnectivity({ repositoryId })}>
              Retry
            </Button>
          </>
        }
      />
    );
  }

  if (isSuccess) {
    return (
      <CheckConnectivityLayout
        title={data.ok ? "Connection Successful" : "Connection Failed"}
        description={data.message}
        actions={
          data.ok ? (
            <Button variant="active" onClick={onClose}>
              Done
            </Button>
          ) : (
            <>
              <Button variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button variant="danger" onClick={() => checkConnectivity({ repositoryId })}>
                Retry
              </Button>
            </>
          )
        }
      />
    );
  }

  // Default: initial state
  return (
    <CheckConnectivityLayout
      title="Check repository connectivity"
      description="Check the connectivity to this repository to validate your connection and authentication status."
      actions={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => checkConnectivity({ repositoryId })}>Check now</Button>
        </>
      }
    />
  );
}

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
  return (
    <Modal isOpen={isOpen} onOpenChange={onOpenChange} className="w-full max-w-lg">
      {({ close }) => <CheckConnectivity repositoryId={repositoryId} onClose={close} />}
    </Modal>
  );
}
