import { Icon } from "@iconify-icon/react";

import InfrahubLogo from "@/assets/Infrahub-SVG-hori.svg?react";

import { Modal } from "@/shared/components/aria/modal";
import { CopyToClipboard } from "@/shared/components/buttons/copy-to-clipboard";
import { Col, Row } from "@/shared/components/container";
import { Skeleton } from "@/shared/components/loading/skeleton";
import { Button } from "@/shared/components/ui/button";
import { capitalizeFirstLetter } from "@/shared/utils/string";

import { useConfig } from "@/entities/config/ui/config-provider";
import { useGetAppInfo } from "@/entities/config/ui/queries/get-app-info.query";

interface AboutModalProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
}

export function AboutModal({ isOpen, onOpenChange }: AboutModalProps) {
  const config = useConfig();
  const { data, isPending, isError } = useGetAppInfo();

  const installationType = `${capitalizeFirstLetter(config.installation_type)} Edition`;
  const version = isPending ? null : isError || !data ? "N/A" : `v${data.version}`;
  const deploymentId = isPending ? null : isError || !data ? "N/A" : data.deployment_id;

  return (
    <Modal
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      aria-label="About Infrahub"
      className="w-full max-w-lg"
    >
      <Row className="justify-between">
        <InfrahubLogo className="h-8" role="img" aria-label="Infrahub logo" />
        <Button variant="ghost" size="icon" onClick={() => onOpenChange(false)} aria-label="Close">
          <Icon icon="mdi:close" className="text-gray-500 text-lg" />
        </Button>
      </Row>

      <Col className="gap-0 rounded-lg bg-gray-50 p-4">
        <InfoRow label="Version" value={version} isPending={isPending} />
        <div className="my-3 h-px bg-gray-200" />
        <InfoRow label="Installation" value={installationType} isPending={false} />
        <div className="my-3 h-px bg-gray-200" />
        <InfoRow label="Deployment ID" value={deploymentId} isPending={isPending} />
      </Col>
    </Modal>
  );
}

function InfoRow({
  label,
  value,
  isPending,
  multiline = false,
}: {
  label: string;
  value: string | null;
  isPending: boolean;
  multiline?: boolean;
}) {
  if (multiline) {
    return (
      <Col className="gap-1.5">
        <Row className="justify-between">
          <span className="text-gray-400 text-sm">{label}</span>
          {!isPending && value && value !== "N/A" && (
            <CopyToClipboard text={value} aria-label={`Copy ${label}`} />
          )}
        </Row>
        {isPending ? (
          <Skeleton className="h-4 w-full" />
        ) : (
          <span className="break-all font-medium text-gray-600 text-sm">{value}</span>
        )}
      </Col>
    );
  }

  return (
    <Row className="justify-between">
      <span className="text-gray-400 text-sm">{label}</span>
      <Row>
        {isPending ? (
          <Skeleton className="h-4 w-20" />
        ) : (
          <>
            <span className="font-semibold text-gray-900 text-sm">{value}</span>
            {value && value !== "N/A" && (
              <CopyToClipboard text={value} aria-label={`Copy ${label}`} />
            )}
          </>
        )}
      </Row>
    </Row>
  );
}
